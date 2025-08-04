# src/dkh/application/services/sync_service.py
import gspread
import structlog
from tortoise.exceptions import DoesNotExist

from dkh.config import settings
from dkh.database.models import Opportunity

logger = structlog.get_logger(__name__)

# Визначаємо назви колонок для зручності
URL_COLUMN_NAME = "Message Link"
MANUAL_STATUS_COLUMN_NAME = "Manual Status"


class SyncService:
    """
    Сервіс для синхронізації ручних статусів з аркуша 'Leads'
    назад у локальну базу даних.
    """

    def __init__(self):
        # --- ✅ ОНОВЛЕНО ---
        # Назва аркуша тепер береться напряму з налаштувань
        self.worksheet_name = settings.google_sheet.leads_sheet_name
        self.worksheet = self._get_worksheet()

    def _get_worksheet(self) -> gspread.Worksheet:
        """Підключається до Google Sheets та отримує потрібний аркуш."""
        logger.info("Connecting to Google Sheets...", worksheet=self.worksheet_name)
        gc = gspread.service_account(filename=str(settings.google_sheet.credentials_path))
        spreadsheet = gc.open_by_key(settings.google_sheet.spreadsheet_id)
        return spreadsheet.worksheet(self.worksheet_name)

    async def run(self):
        """Головний метод, що запускає процес синхронізації."""
        logger.info("Starting sync from Google Sheet to DB...", worksheet=self.worksheet_name)

        all_records = self.worksheet.get_all_records()
        if not all_records:
            logger.warning("Google Sheet is empty. Nothing to sync.")
            return

        updated_count = 0
        for row in all_records:
            message_url = row.get(URL_COLUMN_NAME)
            manual_status = row.get(MANUAL_STATUS_COLUMN_NAME)

            if not message_url or not manual_status:
                continue

            try:
                opportunity = await Opportunity.get(message_url=message_url)

                if opportunity.manual_status != manual_status:
                    opportunity.manual_status = manual_status
                    await opportunity.save()
                    logger.info("Updated status in DB", url=message_url, new_status=manual_status)
                    updated_count += 1

            except DoesNotExist:
                logger.warning("Opportunity not found in DB, skipping.", url=message_url)
            except Exception:
                logger.exception("Failed to update opportunity in DB", url=message_url)

        logger.info("Sync finished.", updated_records=updated_count)
