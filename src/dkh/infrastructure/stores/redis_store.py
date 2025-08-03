# src/dkh/infrastructure/stores/redis_store.py
import redis.asyncio as redis
import structlog
from typing import List

from dkh.domain.ports import SeenMessageStore

logger = structlog.get_logger(__name__)

class RedisSeenMessageStore(SeenMessageStore):
    """
    Реалізація сховища для відстеження оброблених повідомлень за допомогою Redis.

    Використовує структуру даних `SET` в Redis для ефективного зберігання
    та перевірки ID повідомлень для кожного каналу.
    """

    def __init__(self, client: redis.Redis, ttl_seconds: int):
        self._client = client
        self._ttl = ttl_seconds

    def _get_key(self, bot_id: str, channel_id: int) -> str:
        """Створює стандартизований ключ для каналу."""
        return f"seen_messages:{bot_id}:{channel_id}"

    async def mark_as_processed(self, bot_id: str, channel_id: int, message_ids: List[int]) -> None:
        """
        Додає ID повідомлень у `SET` для відповідного каналу та встановлює час життя (TTL).
        """
        if not message_ids:
            return

        key = self._get_key(bot_id, channel_id)
        try:
            # Використовуємо 'pipeline' для атомарного виконання команд
            async with self._client.pipeline() as pipe:
                pipe.sadd(key, *message_ids)
                pipe.expire(key, self._ttl)
                await pipe.execute()
        except redis.RedisError as e:
            logger.error("Failed to mark messages in Redis", key=key, error=e)

    async def is_new(self, bot_id: str, channel_id: int, message_id: int) -> bool:
        """
        Перевіряє, чи існує ID повідомлення в `SET` для даного каналу.
        """
        key = self._get_key(bot_id, channel_id)
        try:
            is_member = await self._client.sismember(key, message_id)
            return not bool(is_member)
        except redis.RedisError as e:
            logger.error("Failed to check message in Redis", key=key, error=e)
            # У разі помилки вважаємо повідомлення старим, щоб уникнути дублікатів
            return False