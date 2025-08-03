from pathlib import Path
from typing import List, Literal, Tuple

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Визначення шляхів ---
# BASE_DIR - корінь проєкту (папка, де лежить 'discord_listener')
# Якщо структура `discord_listener/src/dkh/config/settings.py`, то parents[4]
BASE_DIR = Path(__file__).resolve().parents[3]
CONFIG_FILE = BASE_DIR / 'config.yaml'


# --- Функція-завантажувач для Pydantic ---
def yaml_config_settings_source() -> dict:
    """Завантажує налаштування з YAML, щоб Pydantic міг їх використати."""
    if not CONFIG_FILE.is_file():
        return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


# --- Вкладені моделі для кращої структури ---
class OpenAISettings(BaseModel):
    model: str = 'gpt-4o-mini'
    temperature: float = 0.0
    timeout: int = 30
    max_retries: int = 3
    concurrency: int = 8
    system_prompt: str
    user_prompt_template: str


class DiscordSettings(BaseModel):
    concurrent_channels: int = 12
    batch_pause_seconds: float = 0.3
    delay_seconds: Tuple[float, float] = (0.05, 0.15)
    message_page_limit: int = 100
    max_retries: int = 5
    track_all_channels: bool = True
    channel_whitelist: List[int] = Field(default_factory=list)


class GoogleSheetSettings(BaseModel):
    spreadsheet_id: str
    live_sheet_name: str = 'Live'
    backfill_sheet_name: str = 'Previous'
    stats_sheet_name: str = 'Previous | Stats' # <--- ДОДАЙ ЦЕЙ РЯДОК
    credentials_path: Path = BASE_DIR / 'google_creds.json'


class RedisSettings(BaseModel):
    ttl_days: int = 30
    raw_message_ttl_seconds: int = 3600

    @property
    def message_seen_ttl_seconds(self) -> int:
        """Перетворює дні в секунди для TTL ключів оброблених повідомлень."""
        return self.ttl_days * 24 * 3600


# --- Головна модель налаштувань ---
class Settings(BaseSettings):
    """
    Головна модель конфігурації.
    Завантажує налаштування з YAML, .env файлів та змінних середовища.
    Пріоритет: Змінні середовища > .env > YAML > Значення за замовчуванням.
    """

    # Секрети (з .env або змінних середовища)
    discord_token: SecretStr = Field(..., description='Токен Discord бота')
    openai_api_key: SecretStr = Field(..., description='Ключ до OpenAI API')
    redis_url: SecretStr = Field(
        'redis://localhost:6379/0', description='URL для підключення до Redis'
    )

    # Головні налаштування
    mode: Literal['backfill', 'live'] = 'live'
    history_days: int = 7
    batch_size: int = 500
    concurrency: int = 5
    keywords: List[str] = Field(default_factory=list)

    # Налаштування логування
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    log_dir: Path = BASE_DIR / 'logs'  # Перемістив з config.yaml для надійності
    log_file: str = 'app.log'

    # Вкладені налаштування
    openai: OpenAISettings
    discord: DiscordSettings
    google_sheet: GoogleSheetSettings
    redis: RedisSettings

    # Конфігурація Pydantic-Settings
    model_config = SettingsConfigDict(
        env_prefix='APP_',
        case_sensitive=False,
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore'  # <--- ДОДАЙ ЦЕЙ РЯДОК
    )

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        # Визначаємо порядок джерел: YAML має найнижчий пріоритет
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
            yaml_config_settings_source,  # Наш завантажувач YAML

        )


# Створюємо єдиний екземпляр налаштувань для всього проєкту
settings = Settings()
