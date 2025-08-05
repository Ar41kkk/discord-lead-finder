# src/dkh/application/services/backfill_service.py
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional, AsyncGenerator

import discord
import structlog
from discord.utils import snowflake_time
from tqdm.asyncio import tqdm

from dkh.database.storage import DatabaseStorage
from dkh.application.message_pipeline import MessagePipeline
from dkh.application.utils import SimpleGlobalRateLimiter
from dkh.config import settings
from dkh.domain.models import Message, MessageOpportunity

logger = structlog.get_logger(__name__)


class BackfillService:
    """
    Виконує збір та обробку історії повідомлень з каналів.
    Тепер сервіс спочатку збирає всі потенційні можливості в пам'ять,
    а потім зберігає їх усі разом в кінці однією великою транзакцією.
    """

    def __init__(
            self,
            client: discord.Client,
            pipeline: MessagePipeline,
            rate_limiter: SimpleGlobalRateLimiter,
            db_storage: DatabaseStorage,
    ):
        self.client = client
        self.pipeline = pipeline
        self.rate_limiter = rate_limiter
        self.db = db_storage
        self._channel_semaphore = asyncio.Semaphore(settings.discord.concurrent_channels)

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        if not msg.content:
            return None
        return Message(
            message_id=msg.id,
            channel_id=msg.channel.id,
            channel_name=getattr(msg.channel, 'name', str(msg.channel.id)),
            guild_id=getattr(msg.guild, 'id', None),
            guild_name=getattr(msg.guild, 'name', "Direct Message"),
            author_id=msg.author.id,
            author_name=str(msg.author),
            content=msg.content.strip(),
            timestamp=msg.created_at,
            jump_url=msg.jump_url,
            keyword=None,
        )

    async def run(self):
        bot_id = str(self.client.user.id)
        logger.info("Backfill process started.")

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=settings.history_days)
        active_channels = self._discover_active_channels(cutoff_time)

        if not active_channels:
            logger.warning("No active channels found for backfill. Exiting.")
            return

        all_opportunities = await self._process_channels_history(bot_id, active_channels, cutoff_time)

        if all_opportunities:
            logger.info(f"Collected {len(all_opportunities)} total opportunities. Saving them now...")
            await self.pipeline.recorder.record_batch(all_opportunities, "backfill")
            logger.info("All opportunities have been saved.")
        else:
            logger.info("No new opportunities found during this backfill run.")

        logger.info("Backfill process finished.")

    def _discover_active_channels(self, cutoff: datetime) -> List[discord.TextChannel]:
        active = []
        logger.info("Discovering active channels...")
        for guild in self.client.guilds:
            me = guild.me
            for channel in guild.text_channels:
                if channel.last_message_id and channel.permissions_for(me).read_message_history:
                    try:
                        last_message_time = snowflake_time(channel.last_message_id).replace(tzinfo=timezone.utc)
                        if last_message_time >= cutoff:
                            active.append(channel)
                    except (ValueError, TypeError):
                        continue
        active.sort(key=lambda c: c.last_message_id or 0, reverse=True)
        logger.info("Active channels discovered", count=len(active))
        return active

    async def _process_channels_history(
            self, bot_id: str, channels: List[discord.TextChannel], default_after_time: datetime
    ) -> List[MessageOpportunity]:
        """
        Запускає паралельну обробку каналів і повертає єдиний список всіх знайдених можливостей.
        """
        tasks = [
            self._stream_and_process_channel(channel, bot_id, default_after_time)
            for channel in channels
        ]

        all_opportunities = []
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing Channels"):
            try:
                channel_opportunities = await f
                if channel_opportunities:
                    all_opportunities.extend(channel_opportunities)
            except Exception:
                logger.exception("Error processing channel task")

        return all_opportunities

    # --- ✅ ВИПРАВЛЕНО ---
    async def _stream_and_process_channel(
            self, channel: discord.TextChannel, bot_id: str, default_after_time: datetime
    ) -> List[MessageOpportunity]:
        """
        Створює потоковий конвеєр для одного каналу:
        Читає -> Фільтрує -> Валідує -> Повертає список знайдених можливостей.
        """
        async with self._channel_semaphore:
            last_seen_timestamp = await self.db.get_latest_message_timestamp(channel.id)
            start_time = last_seen_timestamp or default_after_time

            all_tasks_for_channel = []

            async for msg in self._stream_channel_history(channel, start_time):
                if domain_message := self._to_domain_message(msg):
                    task = asyncio.create_task(
                        self.pipeline.validate_and_get_opportunity(domain_message)
                    )
                    all_tasks_for_channel.append(task)

            if not all_tasks_for_channel:
                return []

            # Виконуємо всі створені завдання для цього каналу
            results = await asyncio.gather(*all_tasks_for_channel, return_exceptions=True)

            # Збираємо лише успішні результати (не None і не помилки)
            validated_opportunities = [
                res for res in results
                if res is not None and not isinstance(res, Exception)
            ]

            return validated_opportunities

    async def _stream_channel_history(
            self, channel: discord.TextChannel, after_time: datetime
    ) -> AsyncGenerator[discord.Message, None]:
        last_id, retries = None, 0
        naive_after_time = after_time.replace(tzinfo=None) if after_time.tzinfo else after_time

        while True:
            try:
                await self.rate_limiter.acquire()
                page = [msg async for msg in channel.history(
                    limit=settings.discord.message_page_limit,
                    after=naive_after_time,
                    before=discord.Object(id=last_id) if last_id else None,
                )]
                if not page:
                    break

                for msg in page:
                    yield msg

                last_id, retries = page[-1].id, 0
                await asyncio.sleep(random.uniform(*settings.discord.delay_seconds))
            except discord.Forbidden:
                logger.warning("Permission denied, skipping channel", channel=channel.name)
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    retries += 1
                    retry_after = getattr(e, 'retry_after', 5.0)
                    logger.warning("Rate limit hit, backing off", retry_after=round(retry_after, 2), retries=retries)
                    await asyncio.sleep(retry_after + 1.0)
                    if retries >= settings.discord.max_retries:
                        logger.error("Max retries exceeded for rate limit", channel=channel.name)
                        break
                    continue
                logger.error("Discord HTTP error", status=e.status, channel=channel.name)
                break
            except Exception:
                logger.exception("Unexpected error fetching history", channel_name=channel.name)
                break