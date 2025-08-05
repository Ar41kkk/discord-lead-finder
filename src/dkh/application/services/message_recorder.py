# src/dkh/application/services/message_recorder.py
import asyncio
from typing import List
import structlog

from dkh.config import settings
from dkh.database.storage import DatabaseStorage
from dkh.domain.models import Message, Validation, MessageOpportunity, ValidationStatus
from dkh.domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class MessageRecorder:
    """
    --- ✅ ОНОВЛЕНО ---
    Відповідає за фіналізацію обробки.
    - `record`: для динамічного збереження (режим 'live').
    - `record_batch`: для пакетного збереження в кінці (режим 'backfill').
    """

    def __init__(self, db_storage: DatabaseStorage, sinks: List[OpportunitySink]):
        self._db = db_storage
        self._sinks = sinks

    async def record(self, bot_id: str, message: Message, validation: Validation, source_mode: str):
        """
        Зберігає ОДНЕ успішно валідоване повідомлення. Використовується в 'live' режимі.
        """
        opportunity = MessageOpportunity(message=message, validation=validation)

        # Крок 1: Завжди зберігаємо в базу даних
        saved_record = await self._db.save_opportunity(
            message_data=opportunity.message,
            validation_data=opportunity.validation,
            source_mode=source_mode,
        )

        if not saved_record:
            return

        # Крок 2: Перевіряємо, чи потрібно записувати в Google Sheets
        write_mode = settings.google_sheet.write_mode
        if write_mode == 'qualified':
            is_qualified = validation.status in {ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE}
            if not is_qualified:
                logger.debug(
                    "Skipping Google Sheet write for non-qualified lead",
                    url=opportunity.message.jump_url,
                    status=validation.status.name
                )
                return

        # Крок 3: Якщо перевірка пройдена, зберігаємо в sinks
        if not self._sinks:
            return

        save_tasks = [sink.save([opportunity]) for sink in self._sinks]
        results = await asyncio.gather(*save_tasks, return_exceptions=True)

        for sink, result in zip(self._sinks, results):
            if isinstance(result, Exception):
                logger.error(
                    'Failed to save opportunity to sink',
                    sink=type(sink).__name__,
                    msg_id=message.message_id,
                    error=result,
                )

    # --- ✅ НОВИЙ МЕТОД ---
    async def record_batch(self, opportunities: List[MessageOpportunity], source_mode: str):
        """
        Зберігає ПАКЕТ можливостей. Використовується в 'backfill' режимі.
        """
        if not opportunities:
            return

        logger.info(f"Starting batch recording for {len(opportunities)} opportunities.")

        # Крок 1: Пакетне збереження в базу даних
        # ignore_conflicts=True в bulk_create елегантно обробить дублікати
        saved_count = await self._db.save_opportunities_batch(opportunities, source_mode)
        logger.info(f"Successfully saved {saved_count} new records to the database.")

        # Крок 2: Відфільтровуємо, що писати в Google Sheets, якщо потрібно
        sinks_opportunities = []
        if settings.google_sheet.write_mode == 'qualified':
            sinks_opportunities = [
                opp for opp in opportunities
                if opp.validation.status in {ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE}
            ]
            logger.info(f"Qualified for sinks: {len(sinks_opportunities)} opportunities.")
        else:
            sinks_opportunities = opportunities

        if not self._sinks or not sinks_opportunities:
            return

        # Крок 3: Зберігаємо відфільтровані дані в sinks
        logger.info(f"Saving {len(sinks_opportunities)} opportunities to sinks...")
        save_tasks = [sink.save(sinks_opportunities) for sink in self._sinks]
        results = await asyncio.gather(*save_tasks, return_exceptions=True)

        for sink, result in zip(self._sinks, results):
            if isinstance(result, Exception):
                logger.error(
                    f'Failed to save opportunity batch to sink {type(sink).__name__}',
                    error=result
                )