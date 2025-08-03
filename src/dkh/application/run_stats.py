import json
from datetime import datetime

import structlog

from dkh.config.settings import settings


class RunStatsLogger:
    def __init__(self):
        self.path = settings.log_dir / 'run_stats.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def write(
        self,
        run_started: datetime,
        run_ended: datetime,
        messages_processed: int,
        channels_visited: int,
        guilds_count: int,
        mode: str,
    ):
        data = {
            'run_started': run_started.isoformat(timespec='seconds'),
            'run_ended': run_ended.isoformat(timespec='seconds'),
            'messages_processed': messages_processed,
            'channels_visited': channels_visited,
            'guilds_count': guilds_count,
            'mode': mode,
        }
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger = structlog.get_logger(__name__)
        logger.info('run_stats_written', path=str(self.path), total=messages_processed)
