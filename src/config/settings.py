import yaml
from pathlib import Path
from typing import List, Literal, Tuple, Dict, Any
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = BASE_DIR / 'config.yaml'

def yaml_config_settings_source() -> Dict[str, Any]:
    """
    Джерело налаштувань, що завантажує конфігурацію з файлу config.yaml.
    """
    if not CONFIG_FILE.is_file():
        return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

class DatabaseSettings(BaseModel):
    db_url: str = "sqlite:///db.sqlite3"

class StageOneSettings(BaseModel):
    model: str = 'gpt-3.5-turbo'
    system_prompt: str
    max_retries: int = 1

class StageTwoSettings(BaseModel):
    model: str = 'gpt-4o-mini'
    temperature: float = 0.0
    max_retries: int = 3
    system_prompt: str

class OpenAISettings(BaseModel):
    api_key: SecretStr
    timeout: int = 30
    concurrency: int = 5
    stage_one: StageOneSettings
    stage_two: StageTwoSettings

class DiscordAccount(BaseModel):
    name: str = Field(..., description="Унікальна назва акаунта для ідентифікації")
    token: SecretStr = Field(..., description="Токен Discord акаунта")

class DiscordSettings(BaseModel):
    accounts: List[DiscordAccount] = Field(default_factory=list)
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
    stats_sheet_name: str = 'Stats'
    leads_sheet_name: str = 'Leads'
    credentials_path: Path = BASE_DIR / 'google_creds.json'
    write_mode: Literal['all', 'qualified'] = 'all'

class ExportSettings(BaseModel):
    status_map: Dict[str, str] = Field(default_factory=dict)
    lead_type_map: Dict[str, str] = Field(default_factory=dict)
    default_header: List[str] = Field(default_factory=list)

class Settings(BaseSettings):
    history_days: int = 7
    keywords: List[str] = Field(default_factory=list)
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    log_dir: Path = BASE_DIR / 'logs'
    log_file: str = 'app.log'
    redis_url: str = "redis://127.0.0.1:6379/0"

    database: DatabaseSettings
    openai: OpenAISettings
    discord: DiscordSettings
    google_sheet: GoogleSheetSettings
    export: ExportSettings

    model_config = SettingsConfigDict(
        env_prefix='APP_',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_file=BASE_DIR / '.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ) -> tuple:
        return (init_settings, yaml_config_settings_source, dotenv_settings, file_secret_settings)

settings = Settings()

TORTOISE_CONFIG = {
    "connections": {"default": settings.database.db_url},
    "apps": {"models": {"models": ["database.models"], "default_connection": "default"}},
}