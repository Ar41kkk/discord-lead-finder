import asyncio
from typing import Awaitable, Callable, List, Optional

import discord
import structlog
from discord.ext import commands

from dkh.domain.models import Message

logger = structlog.get_logger(__name__)

# Тип для callback-функції, яку буде викликати лістенер
PipelineCallback = Callable[[Message, str], Awaitable[None]]


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
        # Ініціалізуємо клієнт з self_bot=True і без префікса команд,
        # оскільки команди нам не потрібні. Intents також не вказуємо.
        super().__init__(command_prefix='!', self_bot=True)

        self._pipeline_callback = pipeline_callback
        self._track_all = track_all_channels
        self._target_channels = set(target_channel_ids or [])
        self.remove_command('help')  # Видаляємо стандартну help команду

    async def on_ready(self):
        """Викликається, коли self-bot успішно підключився до Discord."""
        logger.info('✅ Discord Listener is ready.', user=str(self.user), user_id=self.user.id)

    async def on_message(self, message: discord.Message):
        """
        Головний обробник подій. Викликається на кожне нове повідомлення.
        """
        # 1. Ігноруємо власні повідомлення, щоб уникнути нескінченних циклів
        if message.author.id == self.user.id:
            return

        # 2. Фільтруємо канали, якщо не відстежуємо всі
        if not self._track_all and message.channel.id not in self._target_channels:
            return

        # 3. Перетворюємо discord.Message на нашу внутрішню доменну модель
        domain_message = self._to_domain_message(message)
        if not domain_message:
            return

        # 4. Створюємо фонове завдання для обробки повідомлення в пайплайні,
        # щоб не блокувати основний потік обробки подій.
        asyncio.create_task(self._safe_pipeline_call(domain_message))

    async def _safe_pipeline_call(self, domain_message: Message):
        """Безпечно викликає пайплайн, логуючи будь-які помилки."""
        try:
            await self._pipeline_callback(domain_message, str(self.user.id))
        except Exception:
            logger.exception(
                'Unhandled error during message processing pipeline',
                msg_id=domain_message.message_id,
            )

    def _to_domain_message(self, msg: discord.Message) -> Optional[Message]:
        """
        Конвертер з discord.Message в dkh.domain.models.Message.
        Цей метод - серце патерну "Адаптер".
        """
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
