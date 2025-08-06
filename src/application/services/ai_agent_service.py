# src/dkh/application/services/ai_agent_service.py
import instructor
import structlog
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from config import settings
from domain.models import Message, Validation, ValidationStatus

logger = structlog.get_logger(__name__)

# Ініціалізуємо OpenAI-клієнт при старті модуля
try:
    aclient = instructor.patch(AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()))
except Exception as e:
    logger.critical("Failed to initialize OpenAI client. Check API key.", error=e)
    aclient = None


class LeadDetails(BaseModel):
    """Pydantic модель, що описує структуру даних, яку має повернути AI-агент."""
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

    # Загальний лічильник запитів (поділений між усіма інстансами)
    total_requests: int = 0

    def __init__(self):
        self._config = settings.openai

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
        elif score >= 0.5:  # Від 0.5 до 0.85
            return ValidationStatus.POSSIBLY_RELEVANT
        elif score >= 0.1:  # Від 0.1 до 0.5
            return ValidationStatus.POSSIBLY_UNRELEVANT
        else:  # Все, що нижче 0.1
            return ValidationStatus.UNRELEVANT

    async def validate(self, msg: Message) -> Validation:
        """
        Аналізує повідомлення за допомогою OpenAI та повертає структурований результат.
        """
        log = logger.bind(msg_id=msg.message_id, channel_id=msg.channel_id)

        if not aclient:
            log.error("OpenAI client is not available. Skipping validation.")
            return Validation(status=ValidationStatus.ERROR, reason="Client not initialized")

        try:
            # Інкрементуємо глобальний лічильник перед запитом
            AIAgentService.increment_request_count()

            log.info("Sending message to AI Agent for validation...")
            lead_details: LeadDetails = await aclient.chat.completions.create(
                model=self._config.model,
                response_model=LeadDetails,
                messages=[
                    {"role": "system", "content": self._config.system_prompt},
                    {"role": "user", "content": f"Analyze this message:\n---\n{msg.content}\n---"},
                ],
                max_retries=self._config.max_retries,
            )

            status = self._score_to_status(lead_details.confidence, lead_details.is_lead)
            log.debug("Successfully validated message", status=status.name, score=lead_details.confidence)

            return Validation(
                status=status,
                score=lead_details.confidence,
                reason=lead_details.summary,
                lead_type=lead_details.lead_type,
                extracted_tech_stack=lead_details.tech_stack,
            )

        except RateLimitError as e:
            log.warning("OpenAI rate limit exceeded.", error=str(e))
            return Validation(status=ValidationStatus.ERROR, reason="Rate limit exceeded")
        except APITimeoutError as e:
            log.warning("OpenAI request timed out.", error=str(e))
            return Validation(status=ValidationStatus.ERROR, reason="API timeout")
        except APIError as e:
            log.error("OpenAI API error.", code=e.code, message=str(e))
            return Validation(status=ValidationStatus.ERROR, reason=f"API error: {e.code}")
        except Exception as e:
            log.exception("Unexpected error in AI Agent.", error_type=type(e).__name__)
            return Validation(status=ValidationStatus.ERROR, reason="Agent processing failed")