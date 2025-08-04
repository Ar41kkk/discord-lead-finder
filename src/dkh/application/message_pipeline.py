# src/dkh/application/message_pipeline.py
import asyncio
from typing import Optional
import httpx
import structlog

from dkh.config import settings
from dkh.domain.models import Message, ValidationStatus
from .services.message_filter import MessageFilter
from .services.openai_validator import OpenAIValidator
from .services.message_recorder import MessageRecorder
from .services.stats_tracker import StatsTracker

logger = structlog.get_logger(__name__)


class MessagePipeline:
    """
    Керує повним циклом обробки повідомлення.
    Тепер приймає 'recorder' як залежність.
    """

    def __init__(self, recorder: MessageRecorder, stats_tracker: Optional[StatsTracker]):
        """
        Конструктор тепер приймає готовий 'recorder', а не створює його.
        """
        self._recorder = recorder
        self._stats_tracker = stats_tracker

        # Ініціалізація інших залежностей залишається без змін
        self._http_client = httpx.AsyncClient()
        self._openai_semaphore = asyncio.Semaphore(settings.openai.concurrency)
        self._validator = OpenAIValidator(
            client=self._http_client, semaphore=self._openai_semaphore
        )
        self._filter = MessageFilter(settings.keywords)

    async def process_message(self, message: Message, bot_id: str, source_mode: str) -> None:
        """
        Основний метод, який проводить повідомлення через весь конвеєр.
        Тепер він не залежить від 'store' і передає 'source_mode' далі.
        """
        logger.debug("Processing message", msg_id=message.message_id)

        # Перевірка на ключові слова
        if not self._filter.is_relevant(message):
            return

        # Валідація через OpenAI
        validation = await self._validator.validate(message)
        if validation.status == ValidationStatus.ERROR:
            logger.error("OpenAI validation failed, skipping record", msg_id=message.message_id)
            return

        # Оновлення статистики, якщо трекер існує (в режимі backfill)
        if self._stats_tracker:
            self._stats_tracker.track(message, validation)

        # Передача даних на збереження в MessageRecorder
        # База даних сама впорається з дублікатами.
        await self._recorder.record(
            bot_id=bot_id,
            message=message,
            validation=validation,
            source_mode=source_mode,
        )

    async def close(self) -> None:
        """Закриває ресурси, що використовуються пайплайном."""
        await self._http_client.aclose()
        logger.info("MessagePipeline resources closed.")
