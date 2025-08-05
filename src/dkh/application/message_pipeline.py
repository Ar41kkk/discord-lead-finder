# src/dkh/application/message_pipeline.py
import structlog

from dkh.config import settings
from dkh.application.services.ai_agent_service import AIAgentService
from dkh.application.services.message_filter import MessageFilter
from dkh.application.services.message_recorder import MessageRecorder
from dkh.domain.models import Message

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
        self._recorder = recorder
        self._agent = AIAgentService()
        # --- ✅ ВИПРАВЛЕННЯ ТУТ ---
        # Передаємо ключові слова з налаштувань у MessageFilter
        self._filter = MessageFilter(keywords=settings.keywords)

    async def process_message(self, message: Message, bot_id: str, source_mode: str):
        """
        Основний метод, який проводить повідомлення через весь конвеєр.
        """
        logger.debug("Processing message", msg_id=message.message_id)

        # Крок 1: Попередня фільтрація за ключовими словами
        if not self._filter.is_relevant(message):
            return

        # Крок 2: Аналіз повідомлення за допомогою AI-агента
        validation = await self._agent.validate(message)

        # Крок 3: Передача даних на збереження
        await self._recorder.record(
            bot_id=bot_id,
            message=message,
            validation=validation,
            source_mode=source_mode,
        )