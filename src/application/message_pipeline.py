# src/dkh/application/message_pipeline.py
import structlog
from typing import Optional

from config import settings
from application.services.ai_agent_service import AIAgentService
from application.services.message_filter import MessageFilter
from application.services.message_recorder import MessageRecorder
from domain.models import Message, MessageOpportunity

logger = structlog.get_logger(__name__)


class MessagePipeline:
    """
    Керує повним циклом обробки повідомлення, від фільтрації до збереження.
    """

    def __init__(self, recorder: MessageRecorder):
        """
        Конструктор тепер приймає лише 'recorder', оскільки статистика
        більше не збирається на цьому етапі.
        """
        self.recorder = recorder  # --- ✅ Зробив публічним для доступу з backfill_service
        self._agent = AIAgentService()
        self._filter = MessageFilter(keywords=settings.keywords)

    async def process_message(self, message: Message, bot_id: str, source_mode: str):
        """
        Основний метод для режиму 'live'. Проводить повідомлення через весь конвеєр
        і ВІДРАЗУ ЗБЕРІГАЄ результат.
        """
        logger.debug("Processing message", msg_id=message.message_id)

        opportunity = await self.validate_and_get_opportunity(message)

        if opportunity:
            # Крок 3: Передача даних на динамічне збереження
            await self.recorder.record(
                bot_id=bot_id,
                message=opportunity.message,
                validation=opportunity.validation,
                source_mode=source_mode,
            )

    # --- ✅ НОВИЙ МЕТОД ---
    async def validate_and_get_opportunity(self, message: Message) -> Optional[MessageOpportunity]:
        """
        Метод для режиму 'backfill'. Проводить валідацію, але НЕ ЗБЕРІГАЄ,
        а просто повертає знайдений об'єкт MessageOpportunity.
        """
        # Крок 1: Попередня фільтрація за ключовими словами
        if not self._filter.is_relevant(message):
            return None

        # Крок 2: Аналіз повідомлення за допомогою AI-агента
        validation = await self._agent.validate(message)

        # Повертаємо об'єкт, якщо валідація пройшла успішно (навіть якщо статус UNRELEVANT)
        return MessageOpportunity(message=message, validation=validation)