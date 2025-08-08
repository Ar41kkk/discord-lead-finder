# src/application/message_pipeline.py
import structlog
from typing import Optional

from config import settings
from application.services.ai_agent_service import AIAgentService
from application.services.message_filter import MessageFilter
from application.services.message_recorder import MessageRecorder
from domain.models import Message, MessageOpportunity, ValidationStatus, ValidationResult

logger = structlog.get_logger(__name__)


class MessagePipeline:
    """
    Керує повним циклом обробки повідомлення, від фільтрації до збереження.
    """

    def __init__(self, recorder: MessageRecorder):
        self.recorder = recorder
        self._agent = AIAgentService()
        self._filter = MessageFilter(keywords=settings.keywords)

    async def process_message(self, message: Message, bot_id: int, bot_name: str, source_mode: str):
        """
        Основний метод для режиму 'live'.
        """
        logger.debug("Processing message", msg_id=message.message_id)

        opportunity = await self.validate_and_get_opportunity(message)

        if opportunity:
            # Збагачуємо об'єкт інформацією про бота
            opportunity.bot_id = bot_id
            opportunity.bot_name = bot_name

            # --- ОНОВЛЕНИЙ ВИКЛИК ---
            # Прибираємо зайві bot_id та bot_name, оскільки вони вже в 'opportunity'
            await self.recorder.record(
                opportunity=opportunity,
                source_mode=source_mode,
            )

    async def validate_and_get_opportunity(self, message: Message) -> Optional[MessageOpportunity]:
        """
        Виконує повний, двохетапний процес валідації та повертає
        об'єкт MessageOpportunity з результатами.
        """
        if not self._filter.is_relevant(message):
            return None

        stage_one_result = await self._agent.validate_stage_one(message)

        if stage_one_result.status == ValidationStatus.ERROR:
            return MessageOpportunity(message=message, stage_one_validation=stage_one_result)

        stage_two_result: Optional[ValidationResult] = None
        if stage_one_result.status != ValidationStatus.UNRELEVANT:
            stage_two_result = await self._agent.validate_stage_two(message)

        return MessageOpportunity(
            message=message,
            stage_one_validation=stage_one_result,
            stage_two_validation=stage_two_result
        )