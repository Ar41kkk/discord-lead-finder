# src/dkh/config/logging.py
import logging
import logging.handlers
import sys

import structlog

from .settings import settings


def configure_logging() -> None:
    """
    Налаштовує логування для всього додатку, використовуючи structlog.
    Конфігурація розділена для консолі (для розробки) та файлу (для продакшену).
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_file_path = settings.log_dir / settings.log_file
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    # --- Спільні процесори для всіх логерів ---
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),  # Універсальний формат часу
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # --- Налаштування для стандартного logging ---
    logging.basicConfig(
        level=log_level,
        handlers=[logging.NullHandler()],
        force=True,
    )

    # --- Конфігурація structlog ---
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # --- Створення та налаштування хендлерів ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_renderer = structlog.dev.ConsoleRenderer(colors=True)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=console_renderer,
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    file_renderer = structlog.processors.JSONRenderer()
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=file_renderer,
        foreign_pre_chain=shared_processors,
    )
    file_handler.setFormatter(file_formatter)

    # --- Додавання хендлерів до кореневого логера ---
    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler, file_handler]
    root_logger.setLevel(log_level)

    # --- Налаштування рівнів логування для сторонніх бібліотек ---
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    # ✅ **ОСНОВНА ЗМІНА ТУТ**
    # Ми "заглушили" надокучливий логер, встановивши його рівень на ERROR.
    # Тепер він буде показувати тільки справжні помилки.
    logging.getLogger('discord.state').setLevel(logging.ERROR)
    logging.getLogger('discord').setLevel(logging.INFO)

    logger = structlog.get_logger(__name__)
    logger.info('✅ Logging configured successfully', log_level=settings.log_level)