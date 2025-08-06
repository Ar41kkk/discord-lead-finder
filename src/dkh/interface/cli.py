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

# Ініціалізуємо логер та Typer додаток
logger = structlog.get_logger(__name__)
app = typer.Typer(
    help="Інструмент для пошуку лідів у Discord.",
    # ✅ Додаємо красивіші назви для команд у --help
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
        # ✅ Глобальний обробник непередбачуваних помилок
        logger.critical("Application crashed due to an unhandled exception!", exc_info=True)


# --- Команди CLI ---

@app.command()
def live():
    """Запускає бота в режимі реального часу (live)."""
    run_app("live", run_live_mode())

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
        await Tortoise.generate_schemas() # Безпечно створює таблиці, якщо їх немає
        await service_coro
    finally:
        await Tortoise.close_connections()
        logger.info("Database connections closed.")

async def run_live_mode():
    pipeline = bootstrap_live_pipeline()
    client = Listener(
        pipeline_callback=pipeline.process_message,
        track_all_channels=settings.discord.track_all_channels,
        target_channel_ids=settings.discord.channel_whitelist,
    )
    # ✅ Обгортаємо запуск клієнта, щоб гарантовано закрити з'єднання
    await run_with_db(client.start(settings.discord_token.get_secret_value()))


class BackfillClient(discord.Client):
    """Спеціалізований клієнт для режиму backfill, що сам закривається."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finished = asyncio.Event()

    async def on_ready(self):
        logger.info("Backfill client is ready.", user=str(self.user))
        try:
            service = bootstrap_backfill_service(self)
            # ✅ Обгортаємо запуск сервісу
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
        # Запускаємо клієнта і чекаємо, поки він сам себе не закриє
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
