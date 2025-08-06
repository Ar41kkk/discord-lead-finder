# src/dkh/application/message_pipeline.py
import structlog
from typing import Optional

from dkh.config import settings
from dkh.application.services.ai_agent_service import AIAgentService
from dkh.application.services.message_filter import MessageFilter
from dkh.application.services.message_recorder import MessageRecorder
from dkh.domain.models import Message, MessageOpportunity

logger = structlog.get_logger(__name__)


class MessagePipeline:
    """
    Керує повним циклом обробки повідомлення, від фільтрації до збереження.
    """

    def __init__(self, recorder: MessageRecorder):
        """
        Конструктор приймає 'recorder' та ініціалізує внутрішні сервіси.
        """
        self.recorder = recorder
        self._agent = AIAgentService()
        self._filter = MessageFilter(keywords=settings.keywords)

    async def process_message(self, message: Message, bot_id: str, source_mode: str):
        """
        Основний метод для режиму 'live'. Проводить повідомлення через весь конвеєр
        і ВІДРАЗУ ЗБЕРІГАЄ результат.
        """
        log = logger.bind(msg_id=message.message_id, source_mode=source_mode)
        log.debug("Starting message processing in pipeline.")

        opportunity = await self.validate_and_get_opportunity(message)

        if opportunity:
            log.info("Opportunity found, sending to recorder.", status=opportunity.validation.status.name)
            # Передача даних на динамічне збереження
            await self.recorder.record(
                bot_id=bot_id,
                message=opportunity.message,
                validation=opportunity.validation,
                source_mode=source_mode,
            )
        else:
            log.debug("Message did not result in an opportunity.")


    async def validate_and_get_opportunity(self, message: Message) -> Optional[MessageOpportunity]:
        """
        Проводить валідацію, але НЕ ЗБЕРІГАЄ, а просто повертає знайдений
        об'єкт MessageOpportunity. Використовується як 'live', так і 'backfill' режимами.
        """
        log = logger.bind(msg_id=message.message_id)

        # Крок 1: Попередня фільтрація за ключовими словами
        if not self._filter.is_relevant(message):
            log.debug("Message filtered out by keywords.")
            return None

        # Крок 2: Аналіз повідомлення за допомогою AI-агента
        log.debug("Message passed filter, validating with AI Agent...")
        validation = await self._agent.validate(message)

        # Повертаємо об'єкт, якщо валідація пройшла успішно (навіть якщо статус UNRELEVANT)
        return MessageOpportunity(message=message, validation=validation)
