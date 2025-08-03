# src/dkh/application/strategies.py
# encoding: utf-8
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

import discord
import structlog

from dkh.config.settings import settings

if TYPE_CHECKING:
    from ..domain.models import Message
    from .message_pipeline import MessagePipeline

logger = structlog.get_logger(__name__)


class ProcessingStrategy(ABC):
    """Абстрактний базовий клас для стратегії обробки повідомлень."""

    def __init__(self, pipeline: MessagePipeline):
        self.pipeline = pipeline

    async def setup(self) -> None:
        """Виконує початкові налаштування для стратегії."""
        pass

    @abstractmethod
    async def process_message(self, message: discord.Message, bot_id: str) -> None:
        """Обробляє одне вхідне повідомлення."""
        raise NotImplementedError


class LiveProcessingStrategy(ProcessingStrategy):
    """Стратегія для обробки повідомлень в реальному часі."""

    def __init__(self, pipeline: MessagePipeline):
        super().__init__(pipeline)
        self._queue: asyncio.Queue[tuple[str, Message]] = asyncio.Queue(
            maxsize=settings.batch_size * 2
        )
        self._workers: List[asyncio.Task] = []

    async def setup(self) -> None:
        """Налаштовує чергу та фонові воркери для валідації."""
        if self._workers:
            return

        async def worker(idx: int):
            logger.info('validator_worker_started', worker_id=idx)
            while True:
                bot_id, dmsg = await self._queue.get()
                try:
                    await self.pipeline.validate_and_record(bot_id, dmsg)
                except Exception:
                    logger.exception(
                        'worker_processing_failed',
                        worker_id=idx,
                        msg_id=getattr(dmsg, 'message_id', None),
                    )
                finally:
                    self._queue.task_done()

        for i in range(settings.concurrency):
            task = asyncio.create_task(worker(i), name=f'validator-worker-{i}')
            self._workers.append(task)

        await self.pipeline.sink.start_background()

        # періодичний флаш у Excel, щоб не чекати закриття
        async def _periodic_flush():
            while True:
                await asyncio.sleep(5)
                try:
                    await self.pipeline.sink.flush_pending()
                except Exception:
                    logger.exception('periodic_flush_failed')

        asyncio.create_task(_periodic_flush(), name='excel-flusher')

        logger.info('Live processing strategy ready.', workers=len(self._workers))

    async def process_message(self, message: discord.Message, bot_id: str) -> None:
        """Фільтрує повідомлення та додає його до черги на валідацію."""
        keyword = self.pipeline.filter.find_keyword(message.content or '')
        if not keyword:
            return

        try:
            if not await self.pipeline.last_seen.is_new(bot_id, message.channel.id, message.id):
                return
        except Exception:
            # let pipeline handle it later
            pass

        if dmsg := self.pipeline.to_domain_message(message, keyword=keyword):
            await self._queue.put((bot_id, dmsg))
