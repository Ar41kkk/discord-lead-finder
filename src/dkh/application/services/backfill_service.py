# src/dkh/application/services/backfill_service.py
import asyncio
import sys
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
        # Лічильник унікальних запитів до AI API
        self.api_request_count: int = 0

    async def run(self):
        log = logger.bind(
            bot_id=str(self.client.user.id),
            history_days=settings.history_days
        )
        log.info("Backfill process started.")

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=settings.history_days)
        active_channels = self._discover_active_channels(cutoff_time)

        if not active_channels:
            log.warning("No active channels found for backfill. Exiting.")
            return

        all_opportunities = await self._process_channels_history(active_channels, cutoff_time)

        if all_opportunities:
            log.info(f"Collected {len(all_opportunities)} total opportunities. Saving them now...")
            await self.pipeline.recorder.record_batch(all_opportunities, "backfill")
        else:
            log.info("No new opportunities found during this backfill run.")

        # Лог загальної кількості унікальних запитів до AI
        log.info("Total unique AI validation requests made", api_requests=self.api_request_count)
        log.info("Backfill process finished.")

    def _discover_active_channels(self, cutoff: datetime) -> List[discord.TextChannel]:
        active = []
        logger.debug("Discovering active channels...", cutoff_date=cutoff.strftime('%Y-%m-%d'))
        for guild in self.client.guilds:
            log = logger.bind(guild_id=guild.id, guild_name=guild.name)
            me = guild.me
            for channel in guild.text_channels:
                if channel.last_message_id and channel.permissions_for(me).read_message_history:
                    try:
                        last_message_time = snowflake_time(channel.last_message_id).replace(tzinfo=timezone.utc)
                        if last_message_time >= cutoff:
                            active.append(channel)
                    except (ValueError, TypeError):
                        log.debug("Could not parse snowflake_time for channel", channel_id=channel.id)
        active.sort(key=lambda c: c.last_message_id or 0, reverse=True)
        logger.info("Active channels discovered", count=len(active))
        return active

    async def _process_channels_history(
        self,
        channels: List[discord.TextChannel],
        default_after_time: datetime
    ) -> List[MessageOpportunity]:
        tasks = [self._stream_and_process_channel(ch, default_after_time) for ch in channels]

        all_opportunities = []
        processed_count = 0
        failed_count = 0
        progress_bar = tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc="Processing Channels",
            file=sys.stderr
        )
        for f in progress_bar:
            try:
                channel_opportunities = await f
                if channel_opportunities:
                    all_opportunities.extend(channel_opportunities)
                processed_count += 1
            except Exception:
                logger.error("A channel processing task failed. See previous logs for details.")
                failed_count += 1

        logger.info(
            "Finished processing channels history",
            total_channels=len(tasks),
            successful=processed_count,
            failed=failed_count,
            found_opportunities=len(all_opportunities)
        )
        return all_opportunities

    async def _stream_and_process_channel(
        self, channel: discord.TextChannel, default_after_time: datetime
    ) -> List[MessageOpportunity]:
        log = logger.bind(channel_id=channel.id, channel_name=channel.name)
        try:
            async with self._channel_semaphore:
                # ЕТАП 1: ЗБІР ТА ПЕРВИННА ФІЛЬТРАЦІЯ З ДЕДУПЛІКАЦІЄЮ
                last_seen_timestamp = await self.db.get_latest_message_timestamp(channel.id)
                start_time = last_seen_timestamp or default_after_time

                potential_messages: List[Message] = []
                async for msg in self._stream_and_deduped_history(channel, start_time):
                    domain = self._to_domain_message(msg)
                    if domain:
                        potential_messages.append(domain)

                if not potential_messages:
                    return []

                # ЕТАП 2: ДЕДУПЛІКАЦІЯ ЗА URL ТА ПЕРЕВІРКА В БД
                urls = [m.jump_url for m in potential_messages]
                existing = set(await self.db.get_existing_urls(urls))
                unique_map = {}
                for m in potential_messages:
                    if m.jump_url in existing:
                        continue
                    unique_map[m.jump_url] = m
                messages_for_ai = list(unique_map.values())

                if not messages_for_ai:
                    log.debug("No new unique messages to send to AI after DB check.")
                    return []

                # Збільшуємо лічильник унікальних запитів до AI
                self.api_request_count += len(messages_for_ai)
                log.debug(f"Incremented API request counter by {len(messages_for_ai)}. Total so far: {self.api_request_count}")

                log.debug(f"Queue of {len(messages_for_ai)} unique messages for AI validation formed.")

                # ЕТАП 3: КОНТРОЛЬОВАНА ОБРОБКА ЧЕРЕЗ AI
                validation_tasks = [
                    asyncio.create_task(self.pipeline.validate_and_get_opportunity(msg))
                    for msg in messages_for_ai
                ]
                results = await asyncio.gather(*validation_tasks, return_exceptions=True)
                return [res for res in results if res and not isinstance(res, Exception)]
        except Exception as e:
            log.exception("Critical error during channel processing pipeline", error_type=type(e).__name__)
            raise

    async def _stream_and_deduped_history(
        self, channel: discord.TextChannel, after_time: datetime
    ) -> AsyncGenerator[discord.Message, None]:
        """
        Асинхронно ітерується по історії повідомлень з дедуплікацією по ID, щоб уникнути повторів.
        """
        seen_ids = set()
        naive_after = after_time.replace(tzinfo=None)
        while True:
            try:
                await self.rate_limiter.acquire()
                page = [
                    msg async for msg in channel.history(
                        limit=settings.discord.message_page_limit,
                        after=naive_after,
                        before=discord.Object(id=page[-1].id) if 'page' in locals() and page else None,
                    )
                ]
                if not page:
                    break
                for msg in page:
                    if msg.id in seen_ids:
                        continue
                    seen_ids.add(msg.id)
                    yield msg
            except discord.HTTPException as e:
                if e.status == 429:
                    retry_after = float(getattr(e, 'retry_after', 5.0))
                    logger.warning("Rate limit hit, backing off...", retry_after=retry_after)
                    await asyncio.sleep(retry_after + 1)
                    continue
                break
            except Exception:
                logger.exception("Unexpected error fetching channel history")
                break

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        """Конвертує discord.Message в доменну модель Message."""
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
