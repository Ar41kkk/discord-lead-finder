# src/database/storage.py

from datetime import datetime
from typing import Optional, List

from tortoise.exceptions import IntegrityError
from domain.models import MessageOpportunity
from .models import Opportunity, DiscordAccount, Server, Channel, Author


class DatabaseStorage:
    """
    Інкапсулює всю логіку взаємодії з базою даних, включаючи нормалізацію.
    """

    async def save_opportunity(
            self,
            opportunity: MessageOpportunity,
            source_mode: str,
    ) -> Optional[Opportunity]:
        """
        Зберігає ОДНУ можливість, "розумно" створюючи або знаходячи пов'язані сутності.
        """
        try:
            # Тепер беремо дані про бота з об'єкта opportunity
            account, _ = await DiscordAccount.get_or_create(id=opportunity.bot_id,
                                                            defaults={"name": opportunity.bot_name})

            server = None
            if opportunity.message.guild_id and opportunity.message.guild_name:
                server, _ = await Server.get_or_create(id=opportunity.message.guild_id,
                                                       defaults={"name": opportunity.message.guild_name})

            channel, _ = await Channel.get_or_create(
                id=opportunity.message.channel_id,
                defaults={"name": opportunity.message.channel_name, "server": server}
            )

            author, _ = await Author.get_or_create(id=opportunity.message.author_id,
                                                   defaults={"name": opportunity.message.author_name})

            db_opportunity = await Opportunity.create(
                message_url=opportunity.message.jump_url,
                message_content=opportunity.message.content,
                message_timestamp=opportunity.message.timestamp,
                keyword_trigger=opportunity.message.keyword,

                # Посилання на пов'язані об'єкти
                server=server,
                channel=channel,
                author=author,
                discovered_by=account,

                # Результати AI
                ai_stage_one_status=opportunity.stage_one_validation.status.value,
                ai_stage_one_score=opportunity.stage_one_validation.score,
                ai_stage_one_reason=opportunity.stage_one_validation.reason,
                ai_stage_two_status=opportunity.stage_two_validation.status.value if opportunity.stage_two_validation else None,
                ai_stage_two_score=opportunity.stage_two_validation.score if opportunity.stage_two_validation else None,
                ai_stage_two_lead_type=opportunity.stage_two_validation.lead_type if opportunity.stage_two_validation else None,
                ai_stage_two_reason=opportunity.stage_two_validation.reason if opportunity.stage_two_validation else None,

                manual_status='n/a',
                source_mode=source_mode,
            )
            return db_opportunity
        except IntegrityError:
            return None
        except Exception as e:
            print(f"Помилка при збереженні в БД: {e}")
            return None

    async def save_opportunities_batch(
            self,
            opportunities: List[MessageOpportunity],
            bot_id: int,
            bot_name: str,
            source_mode: str,
    ) -> int:
        """
        Зберігає ПАКЕТ можливостей.
        Примітка: для кращої продуктивності в майбутньому цей метод можна оптимізувати,
        щоб він робив менше запитів до БД.
        """
        saved_count = 0
        for opp in opportunities:
            saved = await self.save_opportunity(opp, bot_id, bot_name, source_mode)
            if saved:
                saved_count += 1
        return saved_count

    async def get_latest_message_timestamp(self, channel_id: int) -> Optional[datetime]:
        """
        Знаходить дату ОСТАННЬОГО обробленого повідомлення для конкретного каналу.
        """
        latest_opportunity = await Opportunity.filter(channel_id=channel_id).order_by("-message_timestamp").first()
        if latest_opportunity:
            return latest_opportunity.message_timestamp
        return None

    async def get_existing_urls(self, message_urls: List[str]) -> set[str]:
        """
        Приймає список URL і повертає множину тих URL, які ВЖЕ існують у базі.
        """
        if not message_urls:
            return set()

        existing_records = await Opportunity.filter(message_url__in=message_urls).values_list('message_url', flat=True)
        return set(existing_records)