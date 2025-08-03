# src/dkh/application/services/message_recorder.py
import asyncio
from typing import List
import structlog

from dkh.domain.models import Message, Validation, MessageOpportunity  # <--- ДОДАНО MessageOpportunity
from dkh.domain.ports import OpportunitySink, SeenMessageStore

logger = structlog.get_logger(__name__)


class MessageRecorder:
    """
    Відповідає за фіналізацію обробки: збереження можливостей
    та позначку про те, що повідомлення було оброблене.
    """

    def __init__(self, sinks: List[OpportunitySink], store: SeenMessageStore):
        self._sinks = sinks
        self._store = store

    async def record(self, bot_id: str, message: Message, validation: Validation):
        """
        Зберігає успішно валідоване повідомлення та позначає його як оброблене.
        """
        if not self._sinks:
            logger.warning('No sinks configured. Cannot record opportunity.')
            return

        # --- ✅ ВИПРАВЛЕННЯ ТУТ ---
        # Створюємо правильний об'єкт MessageOpportunity замість словника
        opportunity = MessageOpportunity(message=message, validation=validation)

        # Створюємо завдання для збереження в усі приймачі (Google, Excel, ...)
        save_tasks = [sink.save([opportunity]) for sink in self._sinks]

        # Паралельно виконуємо всі завдання на збереження
        results = await asyncio.gather(*save_tasks, return_exceptions=True)

        for sink, result in zip(self._sinks, results):
            if isinstance(result, Exception):
                logger.error(
                    'Failed to save opportunity to sink',
                    sink=type(sink).__name__,
                    msg_id=message.message_id,
                    error=result,
                )

        # Позначаємо повідомлення як оброблене, щоб не перевіряти його знову
        await self._store.mark_as_processed(
            bot_id, message.channel_id, [message.message_id]
        )