# src/dkh/config/settings.py
from pathlib import Path
from typing import List, Literal, Tuple, Dict, Any

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
CONFIG_FILE = BASE_DIR / 'config.yaml'


# --- ✅ ВИПРАВЛЕННЯ ТУТ ---
# Функція більше не приймає аргумент 'settings',
# що відповідає вимогам нових версій pydantic-settings.
def yaml_config_settings_source() -> Dict[str, Any]:
    """
    Джерело налаштувань, що завантажує конфігурацію з файлу config.yaml.
    """
    if not CONFIG_FILE.is_file():
        return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


class DatabaseSettings(BaseModel):
    """Налаштування підключення до бази даних."""
    db_url: str = "sqlite://db.sqlite3"


class OpenAISettings(BaseModel):
    """Налаштування для OpenAI API."""
    model: str = 'gpt-4o-mini'
    temperature: float = 0.0
    timeout: int = 30
    max_retries: int = 3
    concurrency: int = 5
    system_prompt: str
    user_prompt_template: str


class DiscordSettings(BaseModel):
    """Налаштування для взаємодії з Discord."""
    concurrent_channels: int = 12
    batch_pause_seconds: float = 0.3
    delay_seconds: Tuple[float, float] = (0.05, 0.15)
    message_page_limit: int = 100
    max_retries: int = 5
    track_all_channels: bool = True
    channel_whitelist: List[int] = Field(default_factory=list)


class GoogleSheetSettings(BaseModel):
    """Налаштування для інтеграції з Google Sheets."""
    spreadsheet_id: str
    live_sheet_name: str = 'Live'
    backfill_sheet_name: str = 'Previous'
    stats_sheet_name: str = 'Stats'
    leads_sheet_name: str = 'Leads'
    credentials_path: Path = BASE_DIR / 'google_creds.json'
    write_mode: Literal['all', 'qualified'] = 'all'


class ExportSettings(BaseModel):
    """Налаштування для процесу експорту."""
    status_map: Dict[str, str] = Field(default_factory=dict)
    lead_type_map: Dict[str, str] = Field(default_factory=dict)
    default_header: List[str] = Field(default_factory=list)


class Settings(BaseSettings):
    """
    Головний клас налаштувань, що агрегує всі інші.
    """
    discord_token: SecretStr = Field(..., description='Токен Discord бота')
    openai_api_key: SecretStr = Field(..., description='Ключ до OpenAI API')

    history_days: int = 7
    keywords: List[str] = Field(default_factory=list)
    batch_size: int = 500

    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    log_dir: Path = BASE_DIR / 'logs'
    log_file: str = 'app.log'

    database: DatabaseSettings
    openai: OpenAISettings
    discord: DiscordSettings
    google_sheet: GoogleSheetSettings
    export: ExportSettings

    model_config = SettingsConfigDict(
        env_prefix='APP_',
        case_sensitive=False,
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """
        Визначає пріоритет джерел налаштувань.
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            yaml_config_settings_source,
            file_secret_settings,
        )


settings = Settings()

TORTOISE_CONFIG = {
    "connections": {"default": settings.database.db_url},
    "apps": {
        "models": {
            "models": ["dkh.database.models"],
            "default_connection": "default",
        },
    },
}
