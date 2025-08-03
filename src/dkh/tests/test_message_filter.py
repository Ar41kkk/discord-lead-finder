import pytest
from dkh.application.services.message_filter import MessageFilter
from dkh.domain.models import Message
from datetime import datetime

# Створюємо "заглушку" (mock) повідомлення для тестів
def create_mock_message(content: str) -> Message:
    """Допоміжна функція для створення тестових об'єктів Message."""
    return Message(
        message_id=123,
        channel_id=456,
        channel_name="test-channel",
        guild_id=789,
        guild_name="Test Guild",
        author_id=1,
        author_name="test_user",
        content=content,
        timestamp=datetime.now(),
        jump_url="http://test.com",
    )

def test_filter_finds_keyword():
    """
    Перевіряє, чи фільтр знаходить ключове слово у повідомленні.
    """
    keywords = ["looking for", "dev", "hiring"]
    message_filter = MessageFilter(keywords=keywords)
    message = create_mock_message("Hello, we are hiring a new dev.")

    assert message_filter.is_relevant(message) is True
    # Перевіряємо, що в об'єкті повідомлення тепер є знайдене слово
    assert message.keyword == "hiring"

def test_filter_ignores_irrelevant_message():
    """
    Перевіряє, чи фільтр ігнорує повідомлення без ключових слів.
    """
    keywords = ["looking for", "dev", "hiring"]
    message_filter = MessageFilter(keywords=keywords)
    message = create_mock_message("Hello, this is a general chat message.")

    assert message_filter.is_relevant(message) is False
    assert message.keyword is None

def test_filter_handles_word_boundaries():
    """
    Перевіряє, чи фільтр не знаходить "dev" у слові "develop".
    """
    keywords = ["dev"]
    message_filter = MessageFilter(keywords=keywords)
    message_with_substring = create_mock_message("We need to develop a new feature.")
    message_with_word = create_mock_message("We need a dev for this task.")

    assert message_filter.is_relevant(message_with_substring) is False
    assert message_filter.is_relevant(message_with_word) is True