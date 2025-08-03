from datetime import datetime
from enum import Enum, auto
from typing import Optional

from pydantic import BaseModel


class ValidationStatus(Enum):
    """Статуси валідації повідомлення."""

    RELEVANT = auto()
    HIGH_MAYBE = auto()
    LOW_MAYBE = auto()
    UNRELEVANT = auto()
    ERROR = auto()


class Message(BaseModel):
    """
    Представляє ключову інформацію про одне повідомлення з Discord.
    Це чиста структура даних, незалежна від бібліотеки Discord.
    """

    message_id: int
    channel_id: int
    channel_name: str
    guild_id: Optional[int]
    guild_name: Optional[str]
    author_id: int
    author_name: str
    content: str
    timestamp: datetime
    jump_url: str
    keyword: Optional[str] = None


class Validation(BaseModel):
    """
    Результат валідації одного повідомлення.
    """

    status: ValidationStatus
    score: float = 0.0
    reason: Optional[str] = None
    lead_type: Optional[str] = None


class MessageOpportunity(BaseModel):
    """
    Об'єднує повідомлення та результат його валідації,
    представляючи знайдену "можливість".
    """

    message: Message
    validation: Validation
