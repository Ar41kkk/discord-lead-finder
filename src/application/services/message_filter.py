# src/dkh/application/services/message_filter.py
import re
from typing import List, Optional

import structlog

from domain.models import Message

logger = structlog.get_logger(__name__)


class MessageFilter:
    """
    Відповідає за попередню фільтрацію повідомлень за ключовими словами.
    """

    def __init__(self, keywords: List[str]):
        if not keywords:
            self._keyword_regex = None
            logger.warning("MessageFilter initialized with no keywords. All messages will be processed.")
        else:
            # Створюємо одну велику, ефективну регулярку для всіх ключових слів.
            # `\b` означає "межа слова", щоб "dev" не знаходило в "develop".
            self._keyword_regex = re.compile(
                r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b', re.IGNORECASE
            )
            logger.info("MessageFilter initialized", keyword_count=len(keywords))

    def find_keyword(self, content: str) -> Optional[str]:
        """
        Знаходить перше ключове слово у тексті.

        Returns:
            Знайдене ключове слово або None, якщо нічого не знайдено.
        """
        if not self._keyword_regex:
            return None

        match = self._keyword_regex.search(content)
        return match.group(1) if match else None

    def is_relevant(self, message: Message) -> bool:
        """
        Перевіряє, чи є повідомлення релевантним, і записує знайдене слово.

        Returns:
            True, якщо повідомлення містить хоча б одне ключове слово.
        """
        if not self._keyword_regex:
            # Якщо ключових слів не задано, вважаємо всі повідомлення релевантними.
            return True

        found_keyword = self.find_keyword(message.content)
        if found_keyword:
            # ✅ Зберігаємо знайдене слово в доменну модель
            message.keyword = found_keyword
            logger.debug(
                "Keyword found in message",
                keyword=found_keyword,
                msg_id=message.message_id
            )
            return True

        return False
