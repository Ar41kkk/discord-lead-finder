# src/dkh/application/message_pipeline.py
import asyncio
from typing import List, Optional
import httpx
import structlog

from dkh.config import settings
from dkh.domain.models import Message, ValidationStatus
from dkh.domain.ports import OpportunitySink, SeenMessageStore
from .services.message_filter import MessageFilter
from .services.openai_validator import OpenAIValidator
from .services.message_recorder import MessageRecorder
from .services.stats_tracker import StatsTracker

logger = structlog.get_logger(__name__)


class MessagePipeline:
    """
    Orchestrates the entire message processing flow.
    Manages dependencies and resources like the HTTP client.
    """

    def __init__(self, sinks: List[OpportunitySink], store: SeenMessageStore, stats_tracker: Optional[StatsTracker]):
        self._store = store
        # ✅ FIX HERE: Store the stats_tracker if it's provided
        self._stats_tracker = stats_tracker
        self._http_client = httpx.AsyncClient()
        self._openai_semaphore = asyncio.Semaphore(settings.openai.concurrency)
        self._validator = OpenAIValidator(
            client=self._http_client, semaphore=self._openai_semaphore
        )
        self._filter = MessageFilter(settings.keywords)
        self._recorder = MessageRecorder(sinks=sinks, store=self._store)
        # This is now a simple fallback for live mode
        self._internal_stats = {"processed": 0, "filtered": 0, "opportunities": 0}

    async def process_message(self, message: Message, bot_id: str) -> None:
        """
        The main method that guides a message through the entire pipeline.
        """
        logger.debug("Processing message", msg_id=message.message_id)

        # Use the detailed tracker if available (in backfill mode)
        if self._stats_tracker:
            # The tracker itself will handle the counting
            pass
        else:
            self._internal_stats["processed"] += 1

        if not await self._store.is_new(bot_id, message.channel_id, message.message_id):
            return

        if not self._filter.is_relevant(message):
            if not self._stats_tracker:
                self._internal_stats["filtered"] += 1
            return

        validation = await self._validator.validate(message)
        logger.debug(
            "Validation result",
            msg_id=message.message_id,
            status=validation.status.name,
            score=validation.score
        )

        # If a stats tracker exists, record the result
        if self._stats_tracker and validation.status != ValidationStatus.ERROR:
            self._stats_tracker.track(message, validation)

        # Record the opportunity if it's valid
        if validation.status != ValidationStatus.ERROR:
            is_opportunity = validation.status in {ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE}
            if is_opportunity:
                if not self._stats_tracker:
                    self._internal_stats["opportunities"] += 1

            await self._recorder.record(bot_id, message, validation)
            logger.debug("Validation result recorded", msg_id=message.message_id, status=validation.status.name)
        else:
            logger.error("OpenAI validation failed, skipping record", msg_id=message.message_id)
            await self._store.mark_as_processed(
                bot_id, message.channel_id, [message.message_id]
            )

    def get_stats(self) -> dict:
        """Returns the simple stats for live mode."""
        return self._internal_stats

    async def close(self) -> None:
        """Gracefully closes resources used by the pipeline."""
        await self._http_client.aclose()
        logger.info("MessagePipeline resources closed.")