# src/dkh/bootstrap.py
import discord
import redis.asyncio as redis
import structlog

from dkh.application.message_pipeline import MessagePipeline
from dkh.application.services.backfill_service import BackfillService
from dkh.application.services.stats_tracker import StatsTracker
from dkh.application.utils import SimpleGlobalRateLimiter
from dkh.config import settings
from dkh.infrastructure.sinks.google_sheet import GoogleSheetSink
from dkh.infrastructure.stores.redis_store import RedisSeenMessageStore

logger = structlog.get_logger(__name__)


# Функція для live-режиму (без змін)
def bootstrap_live_pipeline() -> MessagePipeline:
    # ... (код залишається без змін)
    logger.info("Bootstrapping LIVE mode pipeline...")
    sinks = []
    try:
        worksheet_name = settings.google_sheet.live_sheet_name
        sink = GoogleSheetSink.create(settings.google_sheet, worksheet_name)
        sinks.append(sink)
    except Exception as e:
        logger.error("Failed to initialize Google Sheets sink for live mode", error=e)
    redis_client = redis.from_url(settings.redis_url.get_secret_value())
    store = RedisSeenMessageStore(client=redis_client, ttl_seconds=settings.redis.message_seen_ttl_seconds)
    # Для live-режиму передаємо None замість трекера
    pipeline = MessagePipeline(sinks=sinks, store=store, stats_tracker=None)
    logger.info("✅ Live mode pipeline bootstrapped.")
    return pipeline


# Функція для backfill-режиму
def bootstrap_backfill_service(client: discord.Client) -> tuple[BackfillService, StatsTracker]:
    """Builds the service for 'backfill' mode and the stats tracker."""
    logger.info("Bootstrapping BACKFILL mode service...")
    sinks = []
    try:
        worksheet_name = settings.google_sheet.backfill_sheet_name
        sink = GoogleSheetSink.create(settings.google_sheet, worksheet_name)
        sinks.append(sink)
    except Exception as e:
        logger.error("Failed to initialize Google Sheets sink for backfill mode", error=e)

    stats_tracker = StatsTracker(keywords=settings.keywords)
    redis_client = redis.from_url(settings.redis_url.get_secret_value())
    store = RedisSeenMessageStore(client=redis_client, ttl_seconds=settings.redis.message_seen_ttl_seconds)
    pipeline = MessagePipeline(sinks=sinks, store=store, stats_tracker=stats_tracker)
    rate_limiter = SimpleGlobalRateLimiter(interval=0.1)

    # ✅ FIX IS HERE: Add stats_tracker to the constructor call
    backfill_service = BackfillService(
        client=client,
        pipeline=pipeline,
        rate_limiter=rate_limiter,
        stats_tracker=stats_tracker,  # <--- PASS IT IN HERE
    )
    logger.info("✅ Backfill service bootstrapped.")
    return backfill_service, stats_tracker