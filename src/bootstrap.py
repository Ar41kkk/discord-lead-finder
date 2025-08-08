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


def bootstrap_live_dependencies() -> (MessagePipeline, DatabaseStorage):
    """
    Створює та налаштовує залежності для режиму 'live'.
    Повертає конвеєр та сховище даних.
    """
    logger.info("Bootstrapping LIVE mode dependencies...")

    sinks = []
    try:
        sink = GoogleSheetSink.create(config=settings.google_sheet,
                                      worksheet_name=settings.google_sheet.live_sheet_name)
        sinks.append(sink)
    except Exception:
        logger.warning("Could not create Google Sheet sink for live mode. Continuing without it.")

    db_storage = DatabaseStorage()
    recorder = MessageRecorder(db_storage=db_storage, sinks=sinks)
    pipeline = MessagePipeline(recorder=recorder)

    logger.info("✅ Live mode dependencies bootstrapped.")
    return pipeline, db_storage


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
