# src/dkh/application/services/message_recorder.py
import asyncio
from typing import List
import structlog

from dkh.config import settings  # <--- Імпортуємо налаштування
from dkh.database.storage import DatabaseStorage
from dkh.domain.models import Message, Validation, MessageOpportunity, ValidationStatus
from dkh.domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class MessageRecorder:
    """
    Відповідає за фіналізацію обробки: збереження можливостей.
    Спочатку зберігає в БД, а потім в інші джерела (sinks) з урахуванням режиму.
    """

    def __init__(self, db_storage: DatabaseStorage, sinks: List[OpportunitySink]):
        self._db = db_storage
        self._sinks = sinks

    async def record(self, bot_id: str, message: Message, validation: Validation, source_mode: str):
        """
        Зберігає успішно валідоване повідомлення.
        """
        opportunity = MessageOpportunity(message=message, validation=validation)

        # Крок 1: Завжди зберігаємо в базу даних
        saved_record = await self._db.save_opportunity(
            message_data=opportunity.message,
            validation_data=opportunity.validation,
            source_mode=source_mode,
        )

        if not saved_record:
            # Запис вже існує в базі, нічого більше не робимо.
            return

        # --- ✅ НОВА ЛОГІКА ТУТ ---
        # Крок 2: Перевіряємо, чи потрібно записувати в Google Sheets
        write_mode = settings.google_sheet.write_mode
        if write_mode == 'qualified':
            # У режимі "qualified" перевіряємо статус
            is_qualified = validation.status in {ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE}
            if not is_qualified:
                logger.debug(
                    "Skipping Google Sheet write for non-qualified lead",
                    url=opportunity.message.jump_url,
                    status=validation.status.name
                )
                return  # Не записуємо в Google Sheets

        # Крок 3: Якщо перевірка пройдена (або режим "all"), зберігаємо в sinks
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
