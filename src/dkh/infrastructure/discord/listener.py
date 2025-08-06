# src/dkh/infrastructure/discord/listener.py
import asyncio
from typing import Awaitable, Callable, List, Optional

import discord
import structlog
from discord.ext import commands

from dkh.domain.models import Message

logger = structlog.get_logger(__name__)

# Тип для callback-функції, яка буде обробляти повідомлення.
# Очікує: (domain_message, bot_id, source_mode)
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
        logger.info(
            "Discord Listener initialized",
            track_all=self._track_all,
            target_channels=self._target_channels if not self._track_all else "ALL"
        )

    async def on_ready(self):
        logger.info('✅ Discord Listener is ready.', user=str(self.user), user_id=self.user.id)

    async def on_message(self, message: discord.Message):
        log = logger.bind(msg_id=message.id, channel_id=message.channel.id)

        if message.author.id == self.user.id:
            log.debug("Skipping own message.")
            return

        if not self._track_all and message.channel.id not in self._target_channels:
            log.debug("Skipping message from non-target channel.")
            return

        domain_message = self._to_domain_message(message)
        if not domain_message:
            log.debug("Message has no content, skipping.")
            return

        log.debug("Message received and queued for processing.")
        # Запускаємо обробку в фоновому завданні, щоб не блокувати on_message
        asyncio.create_task(self._safe_pipeline_call(domain_message))

    async def _safe_pipeline_call(self, domain_message: Message):
        """Безпечно викликає пайплайн, логуючи будь-які помилки."""
        log = logger.bind(msg_id=domain_message.message_id)
        try:
            # Передаємо "live" як source_mode
            await self._pipeline_callback(domain_message, str(self.user.id), "live")
        except Exception:
            # log.exception автоматично додає повний traceback помилки
            log.exception('Unhandled error during message processing pipeline')

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        """Конвертує discord.Message в доменну модель Message."""
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
