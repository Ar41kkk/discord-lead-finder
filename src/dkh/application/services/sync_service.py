# src/dkh/application/services/sync_service.py
import gspread
import structlog
from tortoise.exceptions import DoesNotExist
from typing import Optional

from dkh.config import settings
from dkh.database.models import Opportunity

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
            all_records = self.worksheet.get_all_records()
            if not all_records:
                log.warning("Google Sheet is empty. Nothing to sync.")
                return

            log.info(f"Found {len(all_records)} records in Google Sheet to process.")
            updated_count = 0

            for i, row in enumerate(all_records):
                message_url = row.get(URL_COLUMN_NAME)
                manual_status = row.get(MANUAL_STATUS_COLUMN_NAME)

                row_log = log.bind(row_num=i + 2, url=message_url)

                if not message_url or not manual_status:
                    row_log.debug("Skipping row with missing URL or Manual Status.")
                    continue

                try:
                    opportunity = await Opportunity.get(message_url=message_url)

                    if opportunity.manual_status != manual_status:
                        opportunity.manual_status = manual_status
                        await opportunity.save()
                        row_log.info("Updated status in DB", new_status=manual_status)
                        updated_count += 1

                except DoesNotExist:
                    # ✅ Змінено на debug, оскільки це очікувана ситуація
                    row_log.debug("Opportunity not found in DB, skipping.")
                except Exception:
                    row_log.exception("Failed to update opportunity in DB")

            log.info("Sync finished.", updated_records=updated_count)
        except Exception:
            log.exception("An unexpected error occurred during the sync process.")

