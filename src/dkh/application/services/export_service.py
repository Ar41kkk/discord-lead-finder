# src/dkh/application/services/export_service.py
import gspread
import structlog
from datetime import timezone

from dkh.config import settings
from dkh.database.models import Opportunity, ValidationStatus
from .stats_generator_service import StatsGeneratorService

logger = structlog.get_logger(__name__)


class ExportService:
    """
    Сервіс для повного експорту даних:
    1. Генерує та вивантажує статистику.
    2. Вивантажує всю базу даних у аркуш 'Leads', адаптуючись до порядку колонок.
    """

    def __init__(self):
        self.stats_generator = StatsGeneratorService()

    async def run(self):
        """Головний метод, що запускає обидва процеси експорту."""
        logger.info("Starting full export process...")
        await self.stats_generator.run()
        await self._export_db_to_sheet()
        logger.info("Full export process finished successfully.")

    async def _export_db_to_sheet(self):
        """
        Витягує всі записи з БД, сортує їх та вивантажує в аркуш 'Leads',
        знаходячи правильні колонки за їхніми назвами в хедері.
        """
        worksheet_name = settings.google_sheet.leads_sheet_name
        logger.info(f"Exporting database to Google Sheet: {worksheet_name}...")

        # --- ✅ СЛОВНИКИ ДЛЯ ГАРНОГО ФОРМАТУВАННЯ ---
        STATUS_MAP = {
            ValidationStatus.RELEVANT: "🔥 Hot Lead",
            ValidationStatus.HIGH_MAYBE: "💡 Good Lead",
            ValidationStatus.LOW_MAYBE: "🤔 Possible",
            ValidationStatus.UNRELEVANT: "❌ Not a Lead",
            ValidationStatus.ERROR: "⚠️ Error",
        }
        LEAD_TYPE_MAP = {
            "direct_hire": "Direct Hire",
            "project_work": "Project Work",
            "paid_help": "Paid Help",
            "other": "Other",
        }

        try:
            gc = gspread.service_account(filename=str(settings.google_sheet.credentials_path))
            spreadsheet = gc.open_by_key(settings.google_sheet.spreadsheet_id)

            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                logger.warning(f"Worksheet '{worksheet_name}' not found. Creating it.")
                header = [
                    "Time", "Server Name", "Channel Name", "Sender Name", "Message Content",
                    "OpenAI Status", "Score", "Type", "Manual Status", "Message Link"
                ]
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1", cols=len(header))
                worksheet.update([header], 'A1')

            sheet_header = worksheet.row_values(1)
            if not sheet_header:
                logger.error("Header row is empty in the Google Sheet. Cannot proceed.")
                return

            opportunities = await Opportunity.all().order_by("-message_timestamp")
            if not opportunities:
                logger.warning("Database is empty. Nothing to export.")
                return

            rows_to_upload = [sheet_header]
            for op in opportunities:
                # --- ✅ ВИКОРИСТОВУЄМО СЛОВНИКИ ДЛЯ ФОРМАТУВАННЯ ---
                formatted_status = STATUS_MAP.get(op.ai_status, op.ai_status.value if op.ai_status else "")
                formatted_type = LEAD_TYPE_MAP.get(op.ai_lead_type, op.ai_lead_type)

                data_map = {
                    "Time": op.message_timestamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "Server Name": op.server_name,
                    "Channel Name": op.channel_name,
                    "Sender Name": op.author_name,
                    "Message Content": op.message_content,
                    "OpenAI Status": formatted_status,
                    "Score": f"{op.ai_score:.0%}" if op.ai_score is not None else "",  # Форматуємо у відсотки
                    "Type": formatted_type,
                    "Manual Status": op.manual_status or "",
                    "Message Link": op.message_url,
                }

                new_row = [data_map.get(column_name, "") for column_name in sheet_header]
                rows_to_upload.append(new_row)

            worksheet.clear()
            worksheet.update(rows_to_upload, 'A1')
            logger.info("Successfully exported database to sheet.", sheet_name=worksheet_name,
                        record_count=len(opportunities))

        except Exception:
            logger.exception("Failed to export database to Google Sheet.")
