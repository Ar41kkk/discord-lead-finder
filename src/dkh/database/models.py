# database/models.py

import enum
from tortoise import fields, models

# Enum для статусів валідації. Гарантує цілісність даних.
class ValidationStatus(str, enum.Enum):
    RELEVANT = "RELEVANT"
    HIGH_MAYBE = "HIGH_MAYBE"
    LOW_MAYBE = "LOW_MAYBE"
    UNRELEVANT = "UNRELEVANT"
    ERROR = "ERROR"

class Opportunity(models.Model):
    """
    Представляє єдину, уніфіковану сутність "можливості",
    що об'єднує дані з Discord та результат аналізу AI.
    """
    # --- Загальна інформація ---
    id = fields.IntField(pk=True)
    message_url = fields.CharField(max_length=255, unique=True, indexed=True, description="Унікальне посилання на повідомлення, наш головний ключ")

    # --- Інформація про джерело (сервер/канал) ---
    server_name = fields.CharField(max_length=100, null=True, description="Назва серверу (Guild)")
    channel_id = fields.BigIntField(indexed=True, description="ID каналу, індексовано для backfill")
    channel_name = fields.CharField(max_length=100, description="Назва каналу")

    # --- Інформація про повідомлення ---
    message_content = fields.TextField(description="Повний текст повідомлення")
    message_timestamp = fields.DatetimeField(indexed=True, description="Час відправки, індексовано для backfill")
    author_id = fields.BigIntField()
    author_name = fields.CharField(max_length=100)
    keyword_trigger = fields.CharField(max_length=100, null=True, description="Ключове слово, яке ініціювало перевірку")

    # --- Результати аналізу AI ---
    ai_status: ValidationStatus = fields.CharEnumField(ValidationStatus, max_length=20, description="Статус від OpenAI")
    ai_score = fields.FloatField(default=0.0, description="Оцінка впевненості від OpenAI")
    ai_lead_type = fields.CharField(max_length=50, null=True, description="Тип співпраці від OpenAI")
    ai_reason = fields.TextField(null=True, description="Пояснення від OpenAI")
    manual_status = fields.CharField(max_length=50, null=True, description="Статус, встановлений вручну користувачем")
    # --- Метадані обробки ---
    source_mode = fields.CharField(max_length=10, description="Режим, в якому знайдено лід ('live' або 'backfill')")
    processed_at = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return f"Opportunity from {self.channel_name}: {self.message_url}"

    class Meta:
        table = "opportunities"