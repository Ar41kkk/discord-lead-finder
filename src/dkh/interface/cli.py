# src/dkh/interface/cli.py
import asyncio
import signal
import typer
import structlog
import discord

from dkh.bootstrap import bootstrap_live_pipeline, bootstrap_backfill_service
from dkh.config import settings, configure_logging
from dkh.infrastructure.discord.listener import Listener

app = typer.Typer()
logger = structlog.get_logger(__name__)


async def run_live_mode():
    """Запускає бота в режимі реального часу."""
    pipeline = bootstrap_live_pipeline()
    client = Listener(
        pipeline_callback=pipeline.process_message,
        track_all_channels=settings.discord.track_all_channels,
        target_channel_ids=settings.discord.channel_whitelist,
    )
    # Запускаємо клієнт з автоматичним керуванням циклом подій
    await client.start(settings.discord_token.get_secret_value())


# Створюємо спеціальний клієнт для backfill режиму
class BackfillClient(discord.Client):
    """Цей клієнт запускається, виконує одне завдання і сам себе закриває."""
    async def on_ready(self):
        logger.info("Backfill client is ready.", user=str(self.user))
        try:
            # Збираємо та запускаємо сервіс, коли клієнт готовий
            service, stats_tracker = bootstrap_backfill_service(self)
            service.stats_tracker = stats_tracker
            await service.run()
        except Exception:
            logger.critical("Backfill service failed during execution", exc_info=True)
        finally:
            logger.info("Backfill logic complete, closing client.")
            await self.close()

async def run_backfill_mode():
    """Запускає бота в режимі збору історії."""
    logger.info("Starting backfill client...")
    client = BackfillClient(self_bot=True)
    await client.start(settings.discord_token.get_secret_value())


@app.command()
def run():
    """Головна функція запуску. Вибирає режим роботи з config.yaml."""
    configure_logging()
    logger.info("Application starting...", mode=settings.mode)

    # Видаляємо складну логіку з graceful shutdown, оскільки
    # client.start() вже коректно її обробляє
    try:
        if settings.mode == 'live':
            asyncio.run(run_live_mode())
        elif settings.mode == 'backfill':
            asyncio.run(run_backfill_mode())
        else:
            logger.error(f"Unknown mode: '{settings.mode}'. Use 'live' or 'backfill'.")
    except KeyboardInterrupt:
        logger.warning("Application interrupted by user.")

if __name__ == '__main__':
    app()