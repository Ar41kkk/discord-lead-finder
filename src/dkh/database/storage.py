# database/storage.py

from datetime import datetime
from typing import Optional, List

from tortoise.exceptions import IntegrityError

from dkh.domain.models import Message as PydanticMessage, Validation as PydanticValidation, MessageOpportunity
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
        Зберігає ОДНУ можливість в одній транзакції.
        """
        try:
            opportunity = await Opportunity.create(
                message_url=message_data.jump_url,
                server_name=message_data.guild_name,
                channel_id=message_data.channel_id,
                channel_name=message_data.channel_name,
                message_content=message_data.content,
                message_timestamp=message_data.timestamp,
                author_id=message_data.author_id,
                author_name=message_data.author_name,
                keyword_trigger=message_data.keyword,
                ai_status=ValidationStatus(validation_data.status.name),
                ai_score=validation_data.score,
                ai_lead_type=validation_data.lead_type,
                ai_reason=validation_data.reason,
                source_mode=source_mode,
            )
            return opportunity
        except IntegrityError:
            return None
        except Exception as e:
            print(f"Помилка при збереженні в БД: {e}")
            return None

    # --- ✅ НОВИЙ МЕТОД ---
    async def save_opportunities_batch(
            self,
            opportunities: List[MessageOpportunity],
            source_mode: str,
    ) -> int:
        """
        Зберігає ПАКЕТ можливостей, використовуючи bulk_create для максимальної ефективності.
        Використовує 'ignore_conflicts', щоб уникнути помилок з дублікатами.
        Повертає кількість реально створених записів.
        """
        if not opportunities:
            return 0

        db_objects = [
            Opportunity(
                message_url=opp.message.jump_url,
                server_name=opp.message.guild_name,
                channel_id=opp.message.channel_id,
                channel_name=opp.message.channel_name,
                message_content=opp.message.content,
                message_timestamp=opp.message.timestamp,
                author_id=opp.message.author_id,
                author_name=opp.message.author_name,
                keyword_trigger=opp.message.keyword,
                ai_status=ValidationStatus(opp.validation.status.name),
                ai_score=opp.validation.score,
                ai_lead_type=opp.validation.lead_type,
                ai_reason=opp.validation.reason,
                source_mode=source_mode,
            )
            for opp in opportunities
        ]

        try:
            # ignore_conflicts=True працює на рівні БД для полів з unique=True
            created_records = await Opportunity.bulk_create(db_objects, ignore_conflicts=True)
            return len(created_records)
        except Exception as e:
            # Логуємо будь-які інші помилки
            print(f"Помилка при пакетному збереженні в БД: {e}")
            return 0

    async def get_latest_message_timestamp(self, channel_id: int) -> Optional[datetime]:
        """
        Знаходить дату ОСТАННЬОГО обробленого повідомлення для конкретного каналу.
        """
        latest_opportunity = await Opportunity.filter(channel_id=channel_id).order_by("-message_timestamp").first()

    async def get_existing_urls(self, message_urls: List[str]) -> set[str]:
        """
        Приймає список URL і повертає множину тих URL, які ВЖЕ існують у базі.
        Це ключовий метод для уникнення повторної обробки.
        """
        if not message_urls:
            return set()

        existing_records = await Opportunity.filter(message_url__in=message_urls).values_list('message_url', flat=True)
        return set(existing_records)