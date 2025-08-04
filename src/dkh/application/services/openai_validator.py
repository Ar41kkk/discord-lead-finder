# src/dkh/application/services/openai_validator.py
import asyncio
import json
import random
from typing import Literal, Optional

import httpx
import structlog
from pydantic import BaseModel, ValidationError

from dkh.config import settings
from dkh.domain.models import Message, Validation, ValidationStatus

logger = structlog.get_logger(__name__)


class _OpenAIResponse(BaseModel):
    is_lead: bool
    confidence: float
    lead_type: Optional[Literal["direct_hire", "project_work", "paid_help", "other", ""]] = None
    summary: Optional[str] = ''


class OpenAIValidator:
    def __init__(self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
        self._client = client
        self._semaphore = semaphore
        self._config = settings.openai
        self._api_url = 'https://api.openai.com/v1/chat/completions'
        self._headers = {
            'Authorization': f'Bearer {settings.openai_api_key.get_secret_value()}',
            'Content-Type': 'application/json',
        }
        self._base_backoff = 0.5

    @staticmethod
    def _score_to_status(score: float, is_lead: bool) -> ValidationStatus:
        if not is_lead:
            return ValidationStatus.UNRELEVANT
        if score >= 0.85:
            return ValidationStatus.RELEVANT
        if score >= 0.6:
            return ValidationStatus.HIGH_MAYBE
        if score > 0.3:
            return ValidationStatus.LOW_MAYBE
        return ValidationStatus.UNRELEVANT

    async def validate(self, msg: Message) -> Validation:
        prompt = self._config.user_prompt_template.format(message=msg.content)
        payload = {
            'model': self._config.model,
            'messages': [
                {'role': 'system', 'content': self._config.system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': self._config.temperature,
            'response_format': {'type': 'json_object'},
        }

        async with self._semaphore:
            for attempt in range(self._config.max_retries):
                try:
                    response = await self._client.post(
                        self._api_url,
                        json=payload,
                        headers=self._headers,
                        timeout=self._config.timeout,
                    )
                    response.raise_for_status()

                    response_json = response.json()
                    content_str = response_json['choices'][0]['message']['content']

                    data = _OpenAIResponse.model_validate_json(content_str)
                    status = self._score_to_status(data.confidence, data.is_lead)

                    return Validation(
                        status=status,
                        score=data.confidence,
                        reason=data.summary,
                        lead_type=data.lead_type
                    )

                # --- ✅ ОНОВЛЕНА ЛОГІКА ТУТ ---
                # Тепер ми "ловимо" всі помилки, пов'язані з HTTP-запитами
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    logger.warning('OpenAI API request failed', exc_info=True, attempt=attempt + 1)
                except (ValidationError, json.JSONDecodeError, KeyError, IndexError) as e:
                    logger.error('Failed to parse/validate OpenAI response', exc_info=True, attempt=attempt + 1)

                if attempt < self._config.max_retries - 1:
                    delay = self._base_backoff * (2 ** attempt) + random.uniform(0, 0.1)
                    await asyncio.sleep(delay)

        logger.error('All retries failed for OpenAI validation', msg_id=msg.message_id)
        return Validation(status=ValidationStatus.ERROR, reason='Max retries exceeded')
