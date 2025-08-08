# src/database/models.py

import enum
from tortoise import fields, models
from domain.models import ValidationStatus


# --- НОВІ, ОКРЕМІ ТАБЛИЦІ (МОДЕЛІ) ---

class DiscordAccount(models.Model):
    id = fields.BigIntField(pk=True, description="Discord User ID цього бота")
    name = fields.CharField(max_length=100, description="Внутрішня назва акаунта з config.yaml")

    def __str__(self):
        return f"{self.name} ({self.id})"


class Server(models.Model):
    id = fields.BigIntField(pk=True, description="Discord Guild ID")
    name = fields.CharField(max_length=100)

    def __str__(self):
        return self.name


class Channel(models.Model):
    id = fields.BigIntField(pk=True, description="Discord Channel ID")
    name = fields.CharField(max_length=100)
    server = fields.ForeignKeyField("models.Server", related_name="channels")

    def __str__(self):
        return f"{self.server.name} > {self.name}"


class Author(models.Model):
    id = fields.BigIntField(pk=True, description="Discord User ID автора повідомлення")
    name = fields.CharField(max_length=100)

    def __str__(self):
        return self.name


# --- ГОЛОВНА, АЛЕ ТЕПЕР ОНОВЛЕНА, ТАБЛИЦЯ ---

class Opportunity(models.Model):
    """
    Представляє єдину можливість, що посилається на інші сутності.
    """
    id = fields.IntField(pk=True)
    message_url = fields.CharField(max_length=255, unique=True, indexed=True)
    message_content = fields.TextField()
    message_timestamp = fields.DatetimeField(indexed=True)
    keyword_trigger = fields.CharField(max_length=100, null=True)

    # --- ЗОВНІШНІ КЛЮЧІ (روابط) ---
    server = fields.ForeignKeyField("models.Server", related_name="opportunities", null=True)
    channel = fields.ForeignKeyField("models.Channel", related_name="opportunities")
    author = fields.ForeignKeyField("models.Author", related_name="opportunities")
    discovered_by = fields.ForeignKeyField("models.DiscordAccount", related_name="discovered_opportunities")

    # --- Результати аналізу AI (без змін) ---
    ai_stage_one_status = fields.CharEnumField(ValidationStatus, max_length=20)
    ai_stage_one_score = fields.FloatField(default=0.0)
    ai_stage_one_reason = fields.TextField(null=True)
    ai_stage_two_status = fields.CharEnumField(ValidationStatus, max_length=20, null=True)
    ai_stage_two_score = fields.FloatField(null=True)
    ai_stage_two_lead_type = fields.CharField(max_length=50, null=True)
    ai_stage_two_reason = fields.TextField(null=True)

    manual_status = fields.CharField(max_length=50, null=True)
    source_mode = fields.CharField(max_length=10)
    processed_at = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return f"Opportunity from {self.channel.name}: {self.message_url}"

    class Meta:
        table = "opportunities"