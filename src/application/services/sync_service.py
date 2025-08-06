# src/dkh/application/services/sync_service.py
import gspread
import structlog
from tortoise.exceptions import DoesNotExist
from typing import Optional

from config import settings
from database.models import Opportunity

logger = structlog.get_logger(__name__)

# Визначаємо назви колонок для зручності та уникнення "магічних рядків"
URL_COLUMN_NAME = "Message Link"
MANUAL_STATUS_COLUMN_NAME = "Manual Status"


class SyncService:
    """
    Сервіс для синхронізації ручних статусів з аркуша 'Leads'
    назад у локальну базу даних.
    """

    def __init__(self):
        self.worksheet_name = settings.google_sheet.leads_sheet_name
        # ✅ Робимо ініціалізацію аркуша безпечною
        self.worksheet: Optional[gspread.Worksheet] = self._get_worksheet()

    def _get_worksheet(self) -> Optional[gspread.Worksheet]:
        """Підключається до Google Sheets та отримує потрібний аркуш."""
        log = logger.bind(worksheet=self.worksheet_name)
        log.info("Connecting to Google Sheets...")
        try:
            gc = gspread.service_account(filename=str(settings.google_sheet.credentials_path))
            spreadsheet = gc.open_by_key(settings.google_sheet.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.worksheet_name)
            log.info("Successfully connected to Google Sheets.")
            return worksheet
        except Exception:
            # ✅ Логуємо повний traceback помилки
            logger.exception("Failed to connect or find worksheet in Google Sheets.")
            return None

    async def run(self):
        """Головний метод, що запускає процес синхронізації."""
        if not self.worksheet:
            logger.error("SyncService cannot run because worksheet was not initialized.")
            return

        log = logger.bind(worksheet=self.worksheet_name)
        log.info("Starting sync from Google Sheet to DB...")

        try:
            # --- КРОК 1: Отримати всі дані з Google Sheets одним запитом ---
            all_records = self.worksheet.get_all_records()
            if not all_records:
                log.warning("Google Sheet is empty. Nothing to sync.")
                return

            log.info(f"Found {len(all_records)} records in Google Sheet to process.")

            # Створюємо словник для швидкого доступу: {url: status}
            urls_from_sheet = {
                row.get(URL_COLUMN_NAME): row.get(MANUAL_STATUS_COLUMN_NAME)
                for row in all_records
                if row.get(URL_COLUMN_NAME) and row.get(MANUAL_STATUS_COLUMN_NAME)
            }

            if not urls_from_sheet:
                log.warning("No rows with both URL and Status found in the sheet.")
                return

            # --- КРОК 2: Отримати всі відповідні записи з БД одним запитом ---
            opportunities_from_db = await Opportunity.filter(message_url__in=urls_from_sheet.keys())

            # Створюємо словник для швидкого доступу до об'єктів БД
            opportunities_map = {op.message_url: op for op in opportunities_from_db}

            # --- КРОК 3: Порівняти дані в пам'яті та підготувати пакет для оновлення ---
            ops_to_update = []
            for url, opportunity in opportunities_map.items():
                new_status = urls_from_sheet.get(url)
                # Перевіряємо, чи статус дійсно змінився
                if new_status and opportunity.manual_status != new_status:
                    opportunity.manual_status = new_status
                    ops_to_update.append(opportunity)
                    log.debug(f"Queued for update: {url}", new_status=new_status)

            # --- КРОК 4: Виконати оновлення одним пакетним запитом, якщо є що оновлювати ---
            if ops_to_update:
                await Opportunity.bulk_update(ops_to_update, fields=['manual_status'])
                log.info("Sync finished.", updated_records=len(ops_to_update))
            else:
                log.info("Sync finished. No records needed an update.")

        except Exception:
            log.exception("An unexpected error occurred during the sync process.")