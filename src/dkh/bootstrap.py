# src/dkh/bootstrap.py
import discord
import structlog

from dkh.database.storage import DatabaseStorage
from dkh.application.message_pipeline import MessagePipeline
from dkh.application.services.backfill_service import BackfillService
from dkh.application.services.message_recorder import MessageRecorder
# --- ✅ ОНОВЛЕНО ---
# StatsTracker більше не потрібен для процесу збору даних
# from dkh.application.services.stats_tracker import StatsTracker
from dkh.application.utils import SimpleGlobalRateLimiter
from dkh.config import settings
from dkh.infrastructure.sinks.google_sheet import GoogleSheetSink

logger = structlog.get_logger(__name__)


def bootstrap_live_pipeline() -> MessagePipeline:
    """Створює конвеєр для режиму 'live' з інтеграцією бази даних."""
    logger.info("Bootstrapping LIVE mode pipeline...")
    sinks = []
    try:
        worksheet_name = settings.google_sheet.live_sheet_name
        sink = GoogleSheetSink.create(settings.google_sheet, worksheet_name)
        sinks.append(sink)
    except Exception as e:
        logger.error("Failed to initialize Google Sheets sink for live mode", error=e)

    db_storage = DatabaseStorage()
    recorder = MessageRecorder(db_storage=db_storage, sinks=sinks)

    # У live режимі stats_tracker не використовується
    pipeline = MessagePipeline(recorder=recorder, stats_tracker=None)
    logger.info("✅ Live mode pipeline bootstrapped.")
    return pipeline


def bootstrap_backfill_service(client: discord.Client) -> BackfillService:
    """Створює сервіс для режиму 'backfill' з інтеграцією бази даних."""
    logger.info("Bootstrapping BACKFILL mode service...")
    sinks = []
    try:
        worksheet_name = settings.google_sheet.backfill_sheet_name
        sink = GoogleSheetSink.create(settings.google_sheet, worksheet_name)
        sinks.append(sink)
    except Exception as e:
        logger.error("Failed to initialize Google Sheets sink for backfill mode", error=e)

    db_storage = DatabaseStorage()
    recorder = MessageRecorder(db_storage=db_storage, sinks=sinks)

    # --- ✅ ОНОВЛЕНО ---
    # Backfill тепер не збирає статистику в реальному часі, тому stats_tracker=None
    pipeline = MessagePipeline(recorder=recorder, stats_tracker=None)
    rate_limiter = SimpleGlobalRateLimiter(interval=0.1)

    backfill_service = BackfillService(
        client=client,
        pipeline=pipeline,
        rate_limiter=rate_limiter,
        # stats_tracker більше не передається
        db_storage=db_storage,
    )
    logger.info("✅ Backfill service bootstrapped.")
    return backfill_service
