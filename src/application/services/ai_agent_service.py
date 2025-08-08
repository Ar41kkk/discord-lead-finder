# src/application/services/ai_agent_service.py
import instructor
import structlog
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from config import settings
from domain.models import Message, ValidationResult, ValidationStatus

logger = structlog.get_logger(__name__)

# Ініціалізуємо OpenAI-клієнт при старті модуля
try:
    # Використовуємо правильний шлях до ключа: settings.openai.api_key
    aclient = instructor.patch(AsyncOpenAI(api_key=settings.openai.api_key.get_secret_value()))
except Exception as e:
    logger.critical("Failed to initialize OpenAI client. Check API key.", error=e)
    aclient = None


class StageOneResult(BaseModel):
    """Pydantic модель для першого, швидкого етапу валідації."""
    verdict: Literal["POTENTIAL", "JUNK"] = Field(
        ...,
        description="Is there any potential for this to be a lead, or is it obvious junk/spam?"
    )
    confidence: float = Field(..., description="Confidence in the verdict from 0.0 to 1.0")
    reason: str = Field(..., description="A very brief (1-2 sentences) reasoning for the verdict.")


class StageTwoResult(BaseModel):
    """Pydantic модель для другого, детального етапу валідації."""
    status: Literal["RELEVANT", "POSSIBLY_RELEVANT", "POSSIBLY_UNRELEVANT", "UNRELEVANT"] = Field(
        ...,
        description="Your final verdict for this message based on the detailed classification rules."
    )
    is_lead: bool = Field(..., description="Чи є це повідомлення потенційним лідом")
    confidence: float = Field(..., description="Впевненість від 0.0 до 1.0")
    lead_type: Optional[Literal["direct_hire", "project_work", "paid_help", "other"]]
    summary: str = Field(..., description="Короткий висновок англійською")
    tech_stack: Optional[List[str]] = Field(None, description="Ключові технології")


class AIAgentService:
    """
    AI-агент, що використовує `instructor` для аналізу повідомлень.
    """
    total_requests: int = 0

    def __init__(self):
        self._config_stage_one = settings.openai.stage_one
        self._config_stage_two = settings.openai.stage_two

    @classmethod
    def increment_request_count(cls, count: int = 1):
        cls.total_requests += count
        logger.debug("AI total_requests incremented", total_requests=cls.total_requests)

    @staticmethod
    def _score_to_status(score: float, is_lead: bool) -> ValidationStatus:
        """
        Перетворює оцінку впевненості у розширений статус валідації.
        """
        if not is_lead:
            return ValidationStatus.UNRELEVANT

        if score >= 0.85:
            return ValidationStatus.RELEVANT
        elif score >= 0.5:
            return ValidationStatus.POSSIBLY_RELEVANT
        elif score >= 0.1:
            return ValidationStatus.POSSIBLY_UNRELEVANT
        else:
            return ValidationStatus.UNRELEVANT

    async def validate_stage_one(self, msg: Message) -> ValidationResult:
        """
        Виконує перший етап перевірки: швидкий фільтр сміття.
        """
        log = logger.bind(msg_id=msg.message_id, stage=1)
        if not aclient:
            log.error("OpenAI client is not available.")
            return ValidationResult(status=ValidationStatus.ERROR, reason="Client not initialized")

        try:
            AIAgentService.increment_request_count()
            log.info("Sending message to AI Agent for validation (Stage 1)...")

            result: StageOneResult = await aclient.chat.completions.create(
                # --- ВИКОРИСТОВУЄМО НАЛАШТУВАННЯ З КОНФІГУ ---
                model=self._config_stage_one.model,
                response_model=StageOneResult,
                messages=[
                    {"role": "system", "content": self._config_stage_one.system_prompt},
                    {"role": "user", "content": f"Analyze this message:\n---\n{msg.content}\n---"},
                ],
                max_retries=self._config_stage_one.max_retries,
            )

            status = ValidationStatus.POSSIBLY_RELEVANT if result.verdict == "POTENTIAL" else ValidationStatus.UNRELEVANT
            log.debug("Stage 1 validation successful.", status=status.name, score=result.confidence)

            return ValidationResult(status=status, score=result.confidence, reason=result.reason)

        except Exception as e:
            log.exception("Unexpected error in AI Agent (Stage 1).")
            return ValidationResult(status=ValidationStatus.ERROR, reason="Agent processing failed")

    async def validate_stage_two(self, msg: Message) -> ValidationResult:
        """
        Виконує другий етап перевірки: детальний аналіз.
        """
        log = logger.bind(msg_id=msg.message_id, stage=2)
        if not aclient:
            log.error("OpenAI client is not available.")
            return ValidationResult(status=ValidationStatus.ERROR, reason="Client not initialized")

        try:
            AIAgentService.increment_request_count()
            log.info("Sending message to AI Agent for validation (Stage 2)...")

            lead_details: StageTwoResult = await aclient.chat.completions.create(
                # --- ВИКОРИСТОВУЄМО НАЛАШТУВАННЯ З КОНФІГУ ---
                model=self._config_stage_two.model,
                response_model=StageTwoResult,
                messages=[
                    {"role": "system", "content": self._config_stage_two.system_prompt},
                    {"role": "user", "content": f"Analyze this message:\n---\n{msg.content}\n---"},
                ],
                max_retries=self._config_stage_two.max_retries,
                temperature=self._config_stage_two.temperature,
            )

            status = self._score_to_status(lead_details.confidence, lead_details.is_lead)
            log.debug("Stage 2 validation successful", status=status.name, score=lead_details.confidence)

            return ValidationResult(
                status=status,
                score=lead_details.confidence,
                reason=lead_details.summary,
                lead_type=lead_details.lead_type,
                extracted_tech_stack=lead_details.tech_stack,
            )
        except (RateLimitError, APITimeoutError, APIError) as e:
            log.warning(f"OpenAI API error during Stage 2: {type(e).__name__}")
            return ValidationResult(status=ValidationStatus.ERROR, reason=f"API error: {str(e)}")
        except Exception as e:
            log.exception("Unexpected error in AI Agent (Stage 2).")
            return ValidationResult(status=ValidationStatus.ERROR, reason="Agent processing failed")