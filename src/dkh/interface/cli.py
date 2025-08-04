# src/dkh/interface/cli.py
import asyncio
import typer
import structlog
import discord
from tortoise import Tortoise

from dkh.bootstrap import bootstrap_live_pipeline, bootstrap_backfill_service
from dkh.config import settings, configure_logging
from dkh.config.settings import TORTOISE_CONFIG
from dkh.infrastructure.discord.listener import Listener
from dkh.application.services.sync_service import SyncService
from dkh.application.services.export_service import ExportService
from dkh.application.services.stats_generator_service import StatsGeneratorService

app = typer.Typer(help="Інструмент для пошуку лідів у Discord.")
logger = structlog.get_logger(__name__)


@app.command()
def live():
    """Запускає бота в режимі реального часу (live)."""
    configure_logging()
    logger.info("Application starting...", mode='live')
    try:
        asyncio.run(run_live_mode())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")


@app.command()
def backfill():
    """Запускає бота в режимі збору історії (backfill)."""
    configure_logging()
    logger.info("Application starting...", mode='backfill')
    try:
        asyncio.run(run_backfill_mode())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")


@app.command()
def sync():
    """Синхронізує ручні статуси з аркуша 'Leads' назад у базу даних."""
    configure_logging()
    logger.info("Application starting...", mode='sync')
    try:
        asyncio.run(run_sync_mode())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")


@app.command()
def export():
    """Запускає повний експорт: генерує статистику та вивантажує всю БД."""
    configure_logging()
    logger.info("Application starting...", mode='export')
    try:
        asyncio.run(run_export_mode())
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")


# --- Допоміжні асинхронні функції ---

async def run_live_mode():
    try:
        await Tortoise.init(config=TORTOISE_CONFIG)
        await Tortoise.generate_schemas()
        pipeline = bootstrap_live_pipeline()
        client = Listener(
            pipeline_callback=pipeline.process_message,
            track_all_channels=settings.discord.track_all_channels,
            target_channel_ids=settings.discord.channel_whitelist,
        )
        await client.start(settings.discord_token.get_secret_value())
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed for live mode.")


# --- ✅ ОНОВЛЕНА ЛОГІКА ТУТ ---
class BackfillClient(discord.Client):
    """Клієнт для режиму backfill, який сигналізує про завершення роботи."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finished = asyncio.Event()

    async def on_ready(self):
        logger.info("Backfill client is ready.", user=str(self.user))
        try:
            await Tortoise.init(config=TORTOISE_CONFIG)
            await Tortoise.generate_schemas()
            service = bootstrap_backfill_service(self)
            await service.run()
        except Exception:
            logger.critical("Backfill service failed during execution", exc_info=True)
        finally:
            await Tortoise.close_connections()
            logger.info("Database connections closed for backfill mode.")
            await self.close()

    async def close(self):
        """Перевизначаємо метод close, щоб він подавав сигнал про завершення."""
        self._finished.set()
        await super().close()

    async def wait_until_finished(self):
        """Метод, який чекає на сигнал про завершення."""
        await self._finished.wait()


async def run_backfill_mode():
    """Запускає бота в режимі збору історії та чекає на завершення."""
    logger.info("Starting backfill client...")
    client = BackfillClient(self_bot=True)
    try:
        # Запускаємо клієнт у фоні
        asyncio.create_task(client.start(settings.discord_token.get_secret_value()))
        # І чекаємо, доки він не подасть сигнал про завершення
        await client.wait_until_finished()
    except KeyboardInterrupt:
        await client.close()


async def run_sync_mode():
    try:
        await Tortoise.init(config=TORTOISE_CONFIG)
        service = SyncService()
        await service.run()
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed for sync mode.")


async def run_export_mode():
    try:
        await Tortoise.init(config=TORTOISE_CONFIG)
        await Tortoise.generate_schemas()
        service = ExportService()
        await service.run()
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed for export mode.")


if __name__ == '__main__':
    app()
