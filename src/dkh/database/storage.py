# database/storage.py

from datetime import datetime
from typing import Optional

from tortoise.exceptions import IntegrityError

from dkh.domain.models import Message as PydanticMessage, Validation as PydanticValidation
from .models import Opportunity, ValidationStatus

class DatabaseStorage:
    """
    Інкапсулює всю логіку взаємодії з базою даних.
    """

    async def save_opportunity(
        self,
        message_data: PydanticMessage,
        validation_data: PydanticValidation,
        source_mode: str,
    ) -> Optional[Opportunity]:
        """
        Зберігає всі дані про можливість в одній транзакції.
        Елегантно обробляє дублікати, повертаючи None, якщо запис вже існує.
        """
        try:
            opportunity = await Opportunity.create(
                # Дані повідомлення
                message_url=message_data.jump_url,
                server_name=message_data.guild_name,
                channel_id=message_data.channel_id,
                channel_name=message_data.channel_name,
                message_content=message_data.content,
                message_timestamp=message_data.timestamp,
                author_id=message_data.author_id,
                author_name=message_data.author_name,
                keyword_trigger=message_data.keyword,

                # Дані аналізу AI
                ai_status=ValidationStatus(validation_data.status.name),
                ai_score=validation_data.score,
                ai_lead_type=validation_data.lead_type,
                ai_reason=validation_data.reason,

                # Метадані
                source_mode=source_mode,
            )
            return opportunity
        except IntegrityError:
            # Ця помилка виникає, якщо message_url (unique=True) вже є в базі.
            # Це очікувана поведінка, ми просто ігноруємо дублікат.
            # print(f"Повідомлення вже існує, пропущено: {message_data.jump_url}")
            return None
        except Exception as e:
            # Логуємо будь-які інші помилки
            print(f"Помилка при збереженні в БД: {e}")
            return None

    async def get_latest_message_timestamp(self, channel_id: int) -> Optional[datetime]:
        """
        Знаходить дату ОСТАННЬОГО обробленого повідомлення для конкретного каналу.
        Це ключова функція для оптимізації режиму `backfill`.
        """
        latest_opportunity = await Opportunity.filter(channel_id=channel_id).order_by("-message_timestamp").first()
        if latest_opportunity:
            return latest_opportunity.message_timestamp
        return None