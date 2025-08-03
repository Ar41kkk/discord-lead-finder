from typing import AsyncGenerator, List, Protocol

from .models import Message, MessageOpportunity

# --------------------------------------------------------------------------
# Примітка: Ми використовуємо 'Protocol' замість 'ABC' (Abstract Base Class).
# Protocol — це більш сучасний та гнучкий спосіб визначення інтерфейсів
# в Python. Він не вимагає явної наслідування.
# --------------------------------------------------------------------------


class OpportunitySink(Protocol):
    """
    Порт (контракт) для "приймачів", які зберігають знайдені можливості.
    Будь-який клас, що хоче зберігати дані, має реалізувати цей метод.
    """

    async def save(self, opportunities: List[MessageOpportunity]) -> None:
        """Зберігає список знайдених можливостей."""
        ...


class SeenMessageStore(Protocol):
    """
    Порт для сховища, яке відстежує вже оброблені повідомлення,
    щоб уникнути їх повторної обробки.
    """

    async def mark_as_processed(self, message_ids: List[int]) -> None:
        """Позначає список ID повідомлень як оброблені."""
        ...

    async def is_new(self, bot_id: str, channel_id: int, message_id: int) -> bool:
        """Перевіряє, чи є повідомлення новим."""
        ...


class MessageSource(Protocol):
    """
    Порт для джерела, яке постачає повідомлення для обробки.
    Це може бути як історія каналу, так і потік нових повідомлень.
    """

    async def fetch_messages(self) -> AsyncGenerator[List[Message], None]:
        """
        Асинхронний генератор, який повертає повідомлення пачками (batch).
        """
        ...
