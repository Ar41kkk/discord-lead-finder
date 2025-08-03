import re
from typing import List, Optional

from dkh.domain.models import Message


class MessageFilter:
    """
    Відповідає за попередню фільтрацію повідомлень за ключовими словами.
    """

    def __init__(self, keywords: List[str]):
        if not keywords:
            self._keyword_regex = None
        else:
            # Створюємо одну велику, ефективну регулярку для всіх ключових слів.
            # `\b` означає "межа слова", щоб "dev" не знаходило в "develop".
            self._keyword_regex = re.compile(
                r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b', re.IGNORECASE
            )

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
        Перевіряє, чи є повідомлення релевантним.

        Returns:
            True, якщо повідомлення містить хоча б одне ключове слово.
        """
        if not self._keyword_regex:
            # Якщо ключових слів не задано, вважаємо всі повідомлення релевантними.
            return True

        # Використовуємо вже знайдене ключове слово, якщо воно є,
        # або шукаємо його знову.
        message.keyword = message.keyword or self.find_keyword(message.content)
        return message.keyword is not None
