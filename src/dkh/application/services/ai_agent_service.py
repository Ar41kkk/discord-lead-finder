# src/dkh/application/services/ai_agent_service.py
import instructor
import structlog
from openai import AsyncOpenAI, RateLimitError, APIError, APITimeoutError
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from dkh.config import settings
from dkh.domain.models import Message, Validation, ValidationStatus

logger = structlog.get_logger(__name__)

try:
    aclient = instructor.patch(AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()))
except Exception as e:
    logger.critical("Failed to initialize OpenAI client. Check API key.", error=e)
    aclient = None


class LeadDetails(BaseModel):
    """Pydantic модель, що описує структуру даних, яку має повернути AI-агент."""
    is_lead: bool = Field(..., description="Чи є це повідомлення потенційним лідом (користувач ПОТРЕБУЄ допомоги)?")
    confidence: float = Field(..., description="Впевненість від 0.0 до 1.0, що це лід. 0.0, якщо is_lead=false.")
    lead_type: Optional[Literal["direct_hire", "project_work", "paid_help", "other"]] = Field(
        None, description="Класифікація потреби: найм, проектна робота, або інше."
    )
    summary: str = Field(..., description="Дуже короткий (одне речення) висновок про потребу користувача англійською.")
    tech_stack: Optional[List[str]] = Field(None, description="Список ключових технологій, згаданих у повідомленні.")


class AIAgentService:
    """
    AI-агент, що використовує `instructor` для надійного аналізу
    повідомлень та витягнення структурованих даних.
    """

    def __init__(self):
        self._config = settings.openai

    @staticmethod
    def _score_to_status(score: float, is_lead: bool) -> ValidationStatus:
        """Перетворює оцінку впевненості у статус валідації."""
        if not is_lead:
            return ValidationStatus.UNRELEVANT
        if score >= 0.85:
            return ValidationStatus.RELEVANT
        if score >= 0.6:
            return ValidationStatus.HIGH_MAYBE
        return ValidationStatus.LOW_MAYBE

    async def validate(self, msg: Message) -> Validation:
        """
        Аналізує повідомлення за допомогою OpenAI та повертає структурований результат.
        """
        log = logger.bind(msg_id=msg.message_id, channel_id=msg.channel_id)

        if not aclient:
            log.error("OpenAI client is not available. Skipping validation.")
            return Validation(status=ValidationStatus.ERROR, reason="OpenAI client not initialized")

        try:
            log.debug("Sending message to AI Agent for validation...")

            lead_details: LeadDetails = await aclient.chat.completions.create(
                model=self._config.model,
                response_model=LeadDetails,
                messages=[
                    {"role": "system", "content": self._config.system_prompt},
                    {"role": "user", "content": f"Analyze this message:\n\n---\n{msg.content}\n---"},
                ],
                max_retries=self._config.max_retries,
            )

            status = self._score_to_status(lead_details.confidence, lead_details.is_lead)
            # ✅ Змінено на debug, щоб не засмічувати консоль
            log.debug("Successfully validated message", status=status.name, score=lead_details.confidence)

            return Validation(
                status=status,
                score=lead_details.confidence,
                reason=lead_details.summary,
                lead_type=lead_details.lead_type,
                extracted_tech_stack=lead_details.tech_stack,
            )
        except RateLimitError as e:
            log.warning("OpenAI rate limit exceeded. Check your plan and usage.", error=str(e))
            return Validation(status=ValidationStatus.ERROR, reason="Rate limit exceeded")
        except APITimeoutError as e:
            log.warning("OpenAI request timed out.", error=str(e))
            return Validation(status=ValidationStatus.ERROR, reason="API timeout")
        except APIError as e:
            log.error("OpenAI API error occurred.", error_code=e.code, error_message=str(e))
            return Validation(status=ValidationStatus.ERROR, reason=f"API error: {e.code}")
        except Exception as e:
            log.exception("An unexpected error occurred in AI Agent.", error_type=type(e).__name__)
            return Validation(status=ValidationStatus.ERROR, reason="Agent processing failed")
