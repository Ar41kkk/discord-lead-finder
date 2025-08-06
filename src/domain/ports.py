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