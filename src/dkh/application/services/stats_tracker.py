# src/dkh/application/services/stats_tracker.py
from collections import defaultdict
from typing import List, Dict

from dkh.domain.models import Message, Validation, ValidationStatus


class StatsTracker:
    """
    Накопичує детальну статистику по серверах та ключових словах
    протягом сесії роботи.
    """

    def __init__(self, keywords: List[str]):
        # {server_name: {'keyword_hits': int, 'openai_success': int}}
        self.server_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # {keyword: {'mentions': int, 'openai_success': int}}
        self.keyword_stats: Dict[str, Dict[str, int]] = {kw: defaultdict(int) for kw in keywords}

    def track(self, message: Message, validation: Validation):
        """Оновлює лічильники на основі одного обробленого повідомлення."""
        server_name = message.guild_name or "Direct Messages"
        keyword = message.keyword

        # Оновлюємо статистику по серверах
        self.server_stats[server_name]['keyword_hits'] += 1

        # Оновлюємо статистику по ключових словах
        if keyword and keyword in self.keyword_stats:
            self.keyword_stats[keyword]['mentions'] += 1

        # Перевіряємо, чи була валідація успішною
        is_opportunity = validation.status in {ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE}
        if is_opportunity:
            self.server_stats[server_name]['openai_success'] += 1
            if keyword and keyword in self.keyword_stats:
                self.keyword_stats[keyword]['openai_success'] += 1