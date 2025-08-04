import asyncio
from typing import Awaitable, Callable, List, Optional

import discord
import structlog
from discord.ext import commands

from dkh.domain.models import Message

logger = structlog.get_logger(__name__)

# --- ✅ ОНОВЛЕННЯ 1 ---
# Тип для callback-функції тепер очікує третій аргумент: source_mode: str
PipelineCallback = Callable[[Message, str, str], Awaitable[None]]


class Listener(commands.Bot):
    """
    Адаптер для Discord API, реалізований як self-bot.
    Слухає повідомлення, перетворює їх у доменну модель
    і передає в MessagePipeline для обробки.
    """

    def __init__(
        self,
        pipeline_callback: PipelineCallback,
        track_all_channels: bool,
        target_channel_ids: Optional[List[int]] = None,
    ):
        super().__init__(command_prefix='!', self_bot=True)

        self._pipeline_callback = pipeline_callback
        self._track_all = track_all_channels
        self._target_channels = set(target_channel_ids or [])
        self.remove_command('help')

    async def on_ready(self):
        logger.info('✅ Discord Listener is ready.', user=str(self.user), user_id=self.user.id)

    async def on_message(self, message: discord.Message):
        if message.author.id == self.user.id:
            return

        if not self._track_all and message.channel.id not in self._target_channels:
            return

        domain_message = self._to_domain_message(message)
        if not domain_message:
            return

        asyncio.create_task(self._safe_pipeline_call(domain_message))

    async def _safe_pipeline_call(self, domain_message: Message):
        """Безпечно викликає пайплайн, логуючи будь-які помилки."""
        try:
            # --- ✅ ОНОВЛЕННЯ 2 ---
            # Додаємо третій аргумент "live" при виклику.
            await self._pipeline_callback(domain_message, str(self.user.id), "live")
        except Exception:
            logger.exception(
                'Unhandled error during message processing pipeline',
                msg_id=domain_message.message_id,
            )

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        if not msg.content:
            return None

        return Message(
            message_id=msg.id,
            channel_id=msg.channel.id,
            channel_name=getattr(msg.channel, 'name', str(msg.channel.id)),
            guild_id=getattr(msg.guild, 'id', None),
            guild_name=getattr(msg.guild, 'name', 'Direct Message'),
            author_id=msg.author.id,
            author_name=str(msg.author),
            content=msg.content.strip(),
            timestamp=msg.created_at,
            jump_url=msg.jump_url,
        )

