# src/dkh/application/services/backfill_service.py
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import discord
import structlog
from discord.utils import snowflake_time
from tqdm.asyncio import tqdm

from dkh.application.message_pipeline import MessagePipeline
from dkh.application.utils import SimpleGlobalRateLimiter
from dkh.config import settings
from dkh.domain.models import Message
from dkh.application.services.stats_tracker import StatsTracker

logger = structlog.get_logger(__name__)


class BackfillService:
    """
    Виконує збір та обробку історії повідомлень з каналів.
    Твоя унікальна логіка збору та ітерації збережена, але інтегрована
    з новою архітектурою для обробки повідомлень.
    """

    def __init__(
            self,
            client: discord.Client,
            pipeline: MessagePipeline,
            rate_limiter: SimpleGlobalRateLimiter,
            stats_tracker: StatsTracker,
    ):
        self.client = client
        self.pipeline = pipeline
        self.rate_limiter = rate_limiter
        self.stats_tracker = stats_tracker
        self._channel_semaphore = asyncio.Semaphore(settings.discord.concurrent_channels)

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        """
        Допоміжний метод для конвертації discord.Message в нашу внутрішню модель.
        Це дозволяє основній частині коду бути незалежною від бібліотеки Discord.
        """
        if not msg.content:
            return None

        keyword = self.pipeline._filter.find_keyword(msg.content)
        if not keyword:
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
            keyword=keyword,
        )

    async def run(self):
        """Головний метод запуску процесу backfill."""
        bot_id = str(self.client.user.id)
        logger.info("Backfill process started.")

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=settings.history_days)
        active_channels = self._discover_active_channels(cutoff_time)

        if not active_channels:
            logger.warning("No active channels found for backfill. Exiting.")
            return

        await self._process_channels_history(bot_id, active_channels, cutoff_time)

        await self._write_stats_to_sheet()
        logger.info("Backfill process finished.")

    def _discover_active_channels(self, cutoff: datetime) -> List[discord.TextChannel]:
        """
        Знаходить активні канали.
        ✅ ТВОЯ ЛОГІКА ПОВНІСТЮ ЗБЕРЕЖЕНА.
        """
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
            self, bot_id: str, channels: List[discord.TextChannel], after_time: datetime
    ):
        """
        Обробляє історію каналів, використовуючи новий централізований пайплайн.
        """

        async def worker(channel: discord.TextChannel):
            """Збирає історію одного каналу та передає кожне повідомлення в пайплайн."""
            async with self._channel_semaphore:
                messages = await self._fetch_single_channel_history(channel, after_time)
                for msg in messages:
                    if domain_message := self._to_domain_message(msg):
                        await self.pipeline.process_message(domain_message, bot_id)

        tasks = [worker(ch) for ch in channels]
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing Channels"):
            try:
                await f
            except Exception:
                logger.exception("Error processing channel task")

    async def _fetch_single_channel_history(
            self, channel: discord.TextChannel, after_time: datetime
    ) -> List[discord.Message]:
        """
        Збирає історію повідомлень з одного каналу.
        ✅ ТВОЯ ЛОГІКА ПОВНІСТЮ ЗБЕРЕЖЕНА, з виправленням обробки помилок.
        """
        all_messages, last_id, retries = [], None, 0
        naive_after_time = after_time.replace(tzinfo=None)

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
                all_messages.extend(page)
                last_id, retries = page[-1].id, 0
                await asyncio.sleep(random.uniform(*settings.discord.delay_seconds))
            except discord.Forbidden:
                logger.warning("Permission denied, skipping channel", channel=channel.name)
                break
            except discord.HTTPException as e:
                # ✅ ОСНОВНЕ ВИПРАВЛЕННЯ ТУТ
                if e.status == 429:
                    retries += 1
                    # Надійно отримуємо час очікування. Якщо його немає, чекаємо 5 секунд.
                    retry_after = getattr(e, 'retry_after', 5.0)
                    logger.warning(
                        "Rate limit hit, backing off",
                        retry_after=round(retry_after, 2),
                        retries=retries,
                    )
                    # Чекаємо вказаний час + 1 секунду про всяк випадок
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
        return all_messages

    async def _write_stats_to_sheet(self):
        """Форматує та записує зібрану статистику в Google Sheets."""
        logger.info("Writing stats to Google Sheet...")
        try:
            # Готуємо дані по серверах
            server_data = []
            for name, data in sorted(self.stats_tracker.server_stats.items()):
                server_data.append([name, data.get('keyword_hits', 0), data.get('openai_success', 0)])

            # Готуємо дані по ключових словах
            keyword_data = []
            for name, data in sorted(self.stats_tracker.keyword_stats.items()):
                keyword_data.append([name, data.get('mentions', 0), data.get('openai_success', 0)])

            # Комбінуємо дані в одну таблицю
            header = ["Server Name", "Keyword Number", "OpenAI Number", "", "Keyword", "Mentions", "OpenAI Number"]
            final_rows = [header]

            num_rows = max(len(server_data), len(keyword_data))
            for i in range(num_rows):
                s_row = server_data[i] if i < len(server_data) else ["", "", ""]
                k_row = keyword_data[i] if i < len(keyword_data) else ["", "", ""]
                final_rows.append(s_row + [""] + k_row)

            # Записуємо в Google Sheet
            config = settings.google_sheet
            gc = gspread.service_account(filename=str(config.credentials_path))
            spreadsheet = gc.open_by_key(config.spreadsheet_id)

            try:
                stats_sheet = spreadsheet.worksheet(config.stats_sheet_name)
                stats_sheet.clear()
            except gspread.WorksheetNotFound:
                stats_sheet = spreadsheet.add_worksheet(title=config.stats_sheet_name, rows="1000", cols="10")

            stats_sheet.update(final_rows, 'A1')
            logger.info("Successfully wrote stats to sheet.", sheet_name=config.stats_sheet_name)

        except Exception:
            logger.exception("Failed to write stats to Google Sheet.")