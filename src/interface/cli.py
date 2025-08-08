# src/dkh/interface/cli.py
import asyncio
import typer
import structlog
import discord
from tortoise import Tortoise
import os
import time
from pathlib import Path
from dotenv import load_dotenv # <-- НОВИЙ ІМПОРТ

# --- НОВА ЛОГІКА ДЛЯ НАДІЙНОГО ЗАВАНТАЖЕННЯ .ENV ---
# Визначаємо корінь проекту і примусово завантажуємо змінні з .env файлу.
# Це гарантує, що токени та ключі будуть доступні, незалежно від способу запуску.
PROJECT_ROOT_FOR_ENV = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT_FOR_ENV / ".env")


from bootstrap import bootstrap_live_pipeline, bootstrap_backfill_service
from config import settings, configure_logging
from config.settings import TORTOISE_CONFIG
from infrastructure.discord.listener import Listener
from application.services.sync_service import SyncService
from application.services.export_service import ExportService
from utils import get_project_root

# --- ЛОГІКА ДЛЯ КЕРУВАННЯ ---
PROJECT_ROOT = get_project_root()
PID_FILE = PROJECT_ROOT / ".bot.pid"

logger = structlog.get_logger(__name__)
app = typer.Typer(
    help="Інструмент для пошуку лідів у Discord.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


# --- Уніфікована функція запуску ---

def run_app(mode: str, coro):
    """Уніфікована функція для запуску будь-якого режиму."""
    try:
        configure_logging()
        logger.info(f"Application starting in '{mode}' mode...")
        asyncio.run(coro)
        logger.info(f"Application finished '{mode}' mode successfully.")
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")
    except Exception:
        logger.critical("Application crashed due to an unhandled exception!", exc_info=True)


# --- Команди CLI ---

@app.command()
def live():
    """Запускає бота в режимі реального часу (live)."""
    # Перевіряємо, чи файл PID вже не існує
    if PID_FILE.exists():
        logger.error("Файл .bot.pid вже існує. Можливо, бот вже запущений.")
        return

    try:
        # Створюємо PID файл одразу при запуску
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        run_app("live", run_live_mode())
    finally:
        # Гарантовано видаляємо PID файл при будь-якому завершенні
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        logger.info("Live-режим зупинено, PID файл очищено.")


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


# --- Асинхронна логіка для кожного режиму ---

async def run_with_db(service_coro):
    """Ініціалізує та закриває з'єднання з БД для сервісу."""
    try:
        await Tortoise.init(config=TORTOISE_CONFIG)
        await Tortoise.generate_schemas()
        await service_coro
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed.")

async def run_live_mode():
    """Асинхронна логіка для live-режиму."""
    pipeline = bootstrap_live_pipeline()
    client = Listener(
        pipeline_callback=pipeline.process_message,
        track_all_channels=settings.discord.track_all_channels,
        target_channel_ids=settings.discord.channel_whitelist,
    )
    try:
        await run_with_db(client.start(settings.discord_token.get_secret_value()))
    except KeyboardInterrupt:
        logger.info("Отримано сигнал KeyboardInterrupt для зупинки.")
    finally:
        if not client.is_closed():
            await client.close()


class BackfillClient(discord.Client):
    """Спеціалізований клієнт для режиму backfill, що сам закривається."""
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
    client = BackfillClient(self_bot=True)
    try:
        await asyncio.gather(
            client.start(settings.discord_token.get_secret_value()),
            client.wait_until_finished()
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        await client.close()


async def run_sync_mode():
    service = SyncService()
    await run_with_db(service.run())


async def run_export_mode():
    service = ExportService()
    await run_with_db(service.run())


if __name__ == '__main__':
    app()
