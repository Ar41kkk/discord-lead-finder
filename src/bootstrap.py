# src/dkh/bootstrap.py
import discord
import structlog

from database.storage import DatabaseStorage
from application.message_pipeline import MessagePipeline
from application.services.backfill_service import BackfillService
from application.services.message_recorder import MessageRecorder
from application.utils import SimpleGlobalRateLimiter
from config import settings
from infrastructure.sinks.google_sheet import GoogleSheetSink

logger = structlog.get_logger(__name__)


def bootstrap_live_pipeline() -> MessagePipeline:
    """
    Створює та налаштовує конвеєр для режиму 'live'.
    """
    logger.info("Bootstrapping LIVE mode pipeline...")

    sinks = []
    try:
        # ✅ Спрощений виклик, передаємо лише назву аркуша
        # має бути
        sink = GoogleSheetSink.create(config=settings.google_sheet,
                                      worksheet_name=settings.google_sheet.live_sheet_name)
        sinks.append(sink)
    except Exception:
        # Помилка вже залогована всередині .create(), тут можна нічого не робити
        logger.warning("Could not create Google Sheet sink for live mode. Continuing without it.")

    db_storage = DatabaseStorage()
    recorder = MessageRecorder(db_storage=db_storage, sinks=sinks)
    pipeline = MessagePipeline(recorder=recorder)

    logger.info("✅ Live mode pipeline bootstrapped.")
    return pipeline


def bootstrap_backfill_service(client: discord.Client) -> BackfillService:
    """
    Створює та налаштовує сервіс для режиму 'backfill'.
    """
    logger.info("Bootstrapping BACKFILL mode service...")

    db_storage = DatabaseStorage()
    sinks = []
    try:
        # має бути
        sink = GoogleSheetSink.create(config=settings.google_sheet,
                                      worksheet_name=settings.google_sheet.live_sheet_name)
        sinks.append(sink)
    except Exception:
        logger.warning("Could not create Google Sheet sink for backfill mode. Continuing without it.")

    recorder = MessageRecorder(db_storage=db_storage, sinks=sinks)
    pipeline = MessagePipeline(recorder=recorder)
    rate_limiter = SimpleGlobalRateLimiter(interval=settings.discord.batch_pause_seconds)

    backfill_service = BackfillService(
        client=client,
        pipeline=pipeline,
        rate_limiter=rate_limiter,
        db_storage=db_storage,
    )

    logger.info("✅ Backfill service bootstrapped.")
    return backfill_service
