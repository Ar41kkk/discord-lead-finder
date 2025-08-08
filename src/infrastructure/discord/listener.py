# src/infrastructure/discord/listener.py

import asyncio
from typing import Awaitable, Callable, List, Optional
import discord
import structlog
from discord.ext import commands
from pathlib import Path
from domain.models import Message

logger = structlog.get_logger(__name__)

# Тип для callback-функції
PipelineCallback = Callable[[Message, int, str, str], Awaitable[None]]

# Єдине кореневе розташування проекту
PROJECT_ROOT = Path(__file__).resolve().parents[3]
STATUS_DIR = PROJECT_ROOT / ".bot_statuses"
STATUS_DIR.mkdir(exist_ok=True)


class Listener(commands.Bot):
    """
    Адаптер для Discord API як self-bot.
    Передає повідомлення в pipeline_callback.
    """

    def __init__(
        self,
        pipeline_callback: PipelineCallback,
        track_all_channels: bool,
        account_name: str,                        # ⏪ обов’язковий, без дефолту
        target_channel_ids: Optional[List[int]] = None,  # ⏩ необов’язковий
    ):
        super().__init__(command_prefix="!", self_bot=True)
        self._pipeline_callback = pipeline_callback
        self._track_all = track_all_channels
        self._target_channels = set(target_channel_ids or [])
        self._account_name = account_name       # ← зберігаємо ім’я акаунта

        self.remove_command("help")
        logger.info(
            "Discord Listener initialized",
            account=account_name,
            track_all=self._track_all,
            target_channels=(self._target_channels if not self._track_all else "ALL"),
        )

    async def on_ready(self):
        logger.info(
            "✅ Discord Listener is ready.",
            user=str(self.user),
            user_id=self.user.id,
        )
        # Пишемо статус-файл під тим самим account_name
        sf = STATUS_DIR / f"{self._account_name}.status"
        sf.write_text("running")

    async def on_message(self, message: discord.Message):
        log = logger.bind(msg_id=message.id, channel_id=message.channel.id)

        if message.author.id == self.user.id:
            log.debug("Skipping own message.")
            return

        if not self._track_all and message.channel.id not in self._target_channels:
            log.debug("Skipping message from non-target channel.")
            return

        domain_msg = self._to_domain_message(message)
        if not domain_msg:
            log.debug("Empty content, skipping.")
            return

        log.debug("Message queued for processing.")
        asyncio.create_task(self._safe_pipeline_call(domain_msg))

    async def _safe_pipeline_call(self, domain_message: Message):
        log = logger.bind(msg_id=domain_message.message_id)
        try:
            await self._pipeline_callback(
                message=domain_message,
                bot_id=self.user.id,
                bot_name=str(self.user),
                source_mode="live",
            )
        except Exception:
            log.exception("Error in message processing pipeline")

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        if not msg.content:
            return None
        return Message(
            message_id=msg.id,
            channel_id=msg.channel.id,
            channel_name=getattr(msg.channel, "name", str(msg.channel.id)),
            guild_id=getattr(msg.guild, "id", None),
            guild_name=getattr(msg.guild, "name", "Direct Message"),
            author_id=msg.author.id,
            author_name=str(msg.author),
            content=msg.content.strip(),
            timestamp=msg.created_at,
            jump_url=msg.jump_url,
        )

    async def close(self):
        # Видаляємо статус-файл при зупинці
        sf = STATUS_DIR / f"{self._account_name}.status"
        sf.unlink(missing_ok=True)
        await super().close()
