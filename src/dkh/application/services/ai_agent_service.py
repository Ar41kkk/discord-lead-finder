# src/dkh/application/services/ai_agent_service.py
import instructor
import structlog
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from dkh.config import settings
from dkh.domain.models import Message, Validation, ValidationStatus

logger = structlog.get_logger(__name__)

# Створюємо клієнт OpenAI, "пропатчений" бібліотекою instructor
# Це дозволяє нам отримувати Pydantic моделі напряму з OpenAI
aclient = instructor.patch(OpenAI(api_key=settings.openai_api_key.get_secret_value()))


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
        if not is_lead:
            return ValidationStatus.UNRELEVANT
        if score >= 0.85:
            return ValidationStatus.RELEVANT
        if score >= 0.6:
            return ValidationStatus.HIGH_MAYBE
        return ValidationStatus.LOW_MAYBE

    async def validate(self, msg: Message) -> Validation:
        try:
            lead_details = aclient.chat.completions.create(
                model=self._config.model,
                response_model=LeadDetails,
                messages=[
                    {"role": "system", "content": self._config.system_prompt},
                    {"role": "user", "content": f"Analyze this message:\n\n---\n{msg.content}\n---"},
                ],
                max_retries=self._config.max_retries,
            )

            status = self._score_to_status(lead_details.confidence, lead_details.is_lead)

            # Повертаємо розширений результат валідації
            return Validation(
                status=status,
                score=lead_details.confidence,
                reason=lead_details.summary,
                lead_type=lead_details.lead_type,
                # Додаємо нові поля, які ми хочемо зберігати
                extracted_tech_stack=lead_details.tech_stack,
            )
        except Exception:
            logger.exception("AI Agent failed to validate message", msg_id=msg.message_id)
            return Validation(status=ValidationStatus.ERROR, reason="Agent processing failed")
