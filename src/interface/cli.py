# src/interface/cli.py

import asyncio
import typer
import structlog
import discord
from tortoise import Tortoise
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Awaitable

# Визначаємо корінь і завантажуємо .env
PROJECT_ROOT_FOR_ENV = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT_FOR_ENV / ".env")

# Імпорти ваших bootstrap-утиліт і налаштувань
from bootstrap import bootstrap_live_dependencies, bootstrap_backfill_service
from config import settings, configure_logging
from config.settings import TORTOISE_CONFIG

# Наш Listener-адаптер
from infrastructure.discord.listener import Listener

# Сервіси для backfill, sync, export
from application.services.sync_service import SyncService
from application.services.export_service import ExportService

from utils import get_project_root

# --- Ініціалізація CLI ---
PROJECT_ROOT = get_project_root()
logger = structlog.get_logger(__name__)
app = typer.Typer(
    help="Інструмент для пошуку лідів у Discord.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def run_app(mode: str, coro: Awaitable[None]):
    """Обгортка для запуску асинхронного коду через asyncio.run."""
    try:
        configure_logging()
        logger.info(f"Application starting in '{mode}' mode...")
        asyncio.run(coro)
        logger.info(f"Application finished '{mode}' mode successfully.")
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")
    except Exception:
        logger.critical("Application crashed due to an unhandled exception!", exc_info=True)


# --- Команда live ---
@app.command()
def live(
    account_name: Optional[str] = typer.Option(
        ..., "--account", "-a", help="Запустити бота для конкретного акаунта."
    )
):
    pid_file = PROJECT_ROOT / f".bot_{account_name}.pid"
    if pid_file.exists():
        logger.error(f"PID-файл {pid_file.name} вже існує. Можливо бот вже запущений.")
        return

    try:
        # Створюємо PID-файл для контролю
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

        coro = run_live_mode(account_name)
        run_app(f"live (account: {account_name})", coro)

    finally:
        # При завершенні завжди видаляємо PID-файл
        if pid_file.exists():
            pid_file.unlink(missing_ok=True)
        logger.info(f"Live-режим зупинено, PID файл {pid_file.name} очищено.")


# --- Інші команди ---
@app.command()
def backfill():
    """Запускає бота в режимі збору історії (backfill)."""
    run_app("backfill", run_backfill_mode())


@app.command()
def sync():
    """Синхронізує ручні статуси з 'Leads' назад у базу даних."""
    run_app("sync", run_sync_mode())


@app.command()
def export():
    """Запускає повний експорт: статистика та вивантаження БД."""
    run_app("export", run_export_mode())


# --- Загальна логіка з DB ---
async def run_with_db(service_coro: Awaitable[None]):
    """Ініціює Tortoise, виконує корутину, закриває з'єднання."""
    try:
        await Tortoise.init(config=TORTOISE_CONFIG)
        await Tortoise.generate_schemas()
        # Гарантуємо, що в таблиці є Backfill-Client
        from database.models import DiscordAccount
        await DiscordAccount.get_or_create(id=0, defaults={"name": "Backfill-Client"})
        await service_coro
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed.")


# --- Проста функція запуску одного клієнта без Redis ---
async def run_client_simple(client: Listener, token: str, account_name: str):
    """Запускає одного бота та обробляє помилки логіна/крешу."""
    try:
        await client.start(token)
    except discord.errors.LoginFailure:
        logger.error(f"ПОМИЛКА ВХОДУ для акаунта '{account_name}'. Перевірте токен.")
    except Exception:
        logger.exception(f"Неочікувана помилка в роботі акаунта '{account_name}'.")
    finally:
        # Переконаємося, що клієнт закриється
        try:
            await client.close()
        except Exception:
            pass


# --- Логіка live-режиму ---
async def run_live_mode(specific_account_name: Optional[str] = None):
    accounts = settings.discord.accounts
    if specific_account_name:
        accounts = [acc for acc in accounts if acc.name == specific_account_name]
        if not accounts:
            logger.error(f"Акаунт '{specific_account_name}' не знайдено.")
            return

    pipeline, _ = bootstrap_live_dependencies()
    tasks = []
    for acc in accounts:
        client = Listener(
            pipeline_callback    = pipeline.process_message,
            track_all_channels   = settings.discord.track_all_channels,
            target_channel_ids   = settings.discord.channel_whitelist,
            account_name         = acc.name          # ← Оце обов’язково!
        )
        token = acc.token.get_secret_value()
        tasks.append(run_client_simple(client, token, acc.name))

    await run_with_db(asyncio.gather(*tasks))


# --- BackfillClient залишається без змін ---
class BackfillClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finished = asyncio.Event()

    async def on_ready(self):
        logger.info("Backfill client is ready.", user=str(self.user))
        try:
            service = bootstrap_backfill_service(self)
            await run_with_db(service.run())
        except Exception:
            logger.critical("Backfill service failed during execution", exc_info=True)
        finally:
            await self.close()

    async def close(self):
        if not self._finished.is_set():
            self._finished.set()
            await super().close()

    async def wait_until_finished(self):
        await self._finished.wait()


async def run_backfill_mode():
    logger.info("Starting backfill client...")
    if not settings.discord.accounts:
        logger.error("Немає акаунтів для запуску backfill.")
        return
    first_token = settings.discord.accounts[0].token.get_secret_value()
    client = BackfillClient(self_bot=True)
    try:
        await asyncio.gather(client.start(first_token), client.wait_until_finished())
    except (KeyboardInterrupt, asyncio.CancelledError):
        await client.close()


# --- Sync і Export ---
async def run_sync_mode():
    service = SyncService()
    await run_with_db(service.run())


async def run_export_mode():
    service = ExportService()
    await run_with_db(service.run())


if __name__ == "__main__":
    app()
