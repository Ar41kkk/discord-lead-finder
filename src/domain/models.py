# src/domain/models.py
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List
from pydantic import BaseModel, Field


class ValidationStatus(Enum):
    """Статуси валідації повідомлення."""

    RELEVANT = "RELEVANT"  # ✅ Однозначно лід
    POSSIBLY_RELEVANT = "POSSIBLY_RELEVANT"  # 🤔 Є великий потенціал, треба дивитись
    POSSIBLY_UNRELEVANT = "POSSIBLY_UNRELEVANT"  # ⚠️ Схоже на шум, але є маленький шанс
    UNRELEVANT = "UNRELEVANT"  # ❌ Однозначно не лід
    ERROR = "ERROR"  # 🚨 Помилка обробки

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


class ValidationResult(BaseModel):
    """
    Базова модель для результату одного етапу валідації.
    """
    status: ValidationStatus
    score: float = 0.0
    reason: Optional[str] = None
    lead_type: Optional[str] = None
    extracted_tech_stack: Optional[List[str]] = None


class MessageOpportunity(BaseModel):
    """
    Об'єднує повідомлення та результати його валідації,
    представляючи знайдену "можливість".
    """
    message: Message
    stage_one_validation: ValidationResult
    stage_two_validation: Optional[ValidationResult] = None

    # --- НОВІ ПОЛЯ ---
    bot_id: Optional[int] = None
    bot_name: Optional[str] = None