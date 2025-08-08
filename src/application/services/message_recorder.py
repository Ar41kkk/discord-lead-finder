# src/dkh/application/services/message_recorder.py
import asyncio
from typing import List
import structlog

from config import settings
from database.storage import DatabaseStorage
from domain.models import Message, Validation, MessageOpportunity, ValidationStatus
from domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class MessageRecorder:
    """
    Відповідає за фіналізацію обробки: збереження в БД та відправку в зовнішні системи.
    - `record`: для динамічного збереження (режим 'live').
    - `record_batch`: для пакетного збереження (режим 'backfill').
    """

    def __init__(self, db_storage: DatabaseStorage, sinks: List[OpportunitySink]):
        self._db = db_storage
        self._sinks = sinks

    async def record(self, bot_id: str, message: Message, validation: Validation, source_mode: str):
        """
        Зберігає ОДНУ успішно валідовану можливість. Використовується в 'live' режимі.
        """
        log = logger.bind(
            msg_id=message.message_id,
            url=message.jump_url,
            status=validation.status.name
        )
        log.debug("Recording opportunity...")

        opportunity = MessageOpportunity(message=message, validation=validation)

        # Крок 1: Завжди зберігаємо в базу даних
        saved_record = await self._db.save_opportunity(
            message_data=opportunity.message,
            validation_data=opportunity.validation,
            source_mode=source_mode,
        )

        if not saved_record:
            log.warning("Record already exists in DB, skipping further processing.")
            return

        log.debug("Opportunity successfully saved to database.")

        # Крок 2: Перевіряємо, чи потрібно записувати в зовнішні системи (sinks)
        write_mode = settings.google_sheet.write_mode
        if write_mode == 'qualified':
            is_qualified = validation.status in {ValidationStatus.RELEVANT, ValidationStatus.POSSIBLY_RELEVANT}
            if not is_qualified:
                log.debug("Skipping sinks write for non-qualified lead.")
                return

        # Крок 3: Якщо перевірка пройдена, асинхронно зберігаємо в усі sinks
        if not self._sinks:
            return

        log.debug("Sending opportunity to sinks...", sink_count=len(self._sinks))
        save_tasks = [sink.save([opportunity]) for sink in self._sinks]
        results = await asyncio.gather(*save_tasks, return_exceptions=True)

        for sink, result in zip(self._sinks, results):
            if isinstance(result, Exception):
                log.error(
                    'Failed to save opportunity to sink',
                    sink=type(sink).__name__,
                    error=result,
                )

    async def record_batch(self, opportunities: List[MessageOpportunity], source_mode: str):
        """
        Зберігає ПАКЕТ можливостей. Використовується в 'backfill' режимі.
        """
        if not opportunities:
            return

        log = logger.bind(batch_size=len(opportunities), source_mode=source_mode)
        log.info("Starting batch recording.")

        # Крок 1: Пакетне збереження в базу даних
        saved_count = await self._db.save_opportunities_batch(opportunities, source_mode)
        log.info("Batch save to database complete.", new_records=saved_count)

        # Крок 2: Відфільтровуємо, що писати в sinks
        sinks_opportunities = opportunities
        if settings.google_sheet.write_mode == 'qualified':
            sinks_opportunities = [
                opp for opp in opportunities
                if opp.validation.status in {ValidationStatus.RELEVANT, ValidationStatus.POSSIBLY_RELEVANT}
            ]
            log.info("Filtered for sinks.", qualified_count=len(sinks_opportunities))

        if not self._sinks or not sinks_opportunities:
            log.debug("No opportunities to send to sinks.")
            return

        # Крок 3: Зберігаємо відфільтровані дані в sinks
        log.info(f"Sending batch to sinks...")
        save_tasks = [sink.save(sinks_opportunities) for sink in self._sinks]
        results = await asyncio.gather(*save_tasks, return_exceptions=True)

        for sink, result in zip(self._sinks, results):
            if isinstance(result, Exception):
                # ✅ Додаємо traceback до логу помилки
                log.exception(
                    f'Failed to save opportunity batch to sink',
                    sink=type(sink).__name__,
                    error=result
                )
