# src/dkh/infrastructure/sinks/google_sheet.py
import gspread
import structlog
from typing import List

from config.settings import GoogleSheetSettings
from domain.models import MessageOpportunity, ValidationStatus
from domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class GoogleSheetSink(OpportunitySink):
    """
    Реалізація 'приймача' даних, що записує можливості в Google Sheets.
    Форматує дані у зрозумілий для людини вигляд.
    """
    # --- ✅ Оновлені, більш зрозумілі заголовки ---
    HEADER = [
        "Time", "Server Name", "Channel Name", "Sender Name", "Message Content",
        "Status", "Confidence", "Lead Type", "Message Link"
    ]

    # --- ✅ Нові "словники-перекладачі" для гарного форматування ---
    STATUS_MAP = {
        ValidationStatus.RELEVANT: "🔥 Hot Lead",
        ValidationStatus.POSSIBLY_RELEVANT: "💡 Good Lead",
        ValidationStatus.POSSIBLY_UNRELEVANT: "🤔 Possible",
        ValidationStatus.UNRELEVANT: "❌ Not a Lead",
        ValidationStatus.ERROR: "⚠️ Error",
    }

    LEAD_TYPE_MAP = {
        "direct_hire": "Direct Hire",
        "project_work": "Project Work",
        "paid_help": "Paid Help",
        "other": "Other",
    }

    def __init__(self, worksheet: gspread.Worksheet):
        self._worksheet = worksheet
        self._ensure_header()

    @classmethod
    def create(cls, config: GoogleSheetSettings, worksheet_name: str) -> "GoogleSheetSink":
        try:
            gc = gspread.service_account(filename=str(config.credentials_path))
            spreadsheet = gc.open_by_key(config.spreadsheet_id)
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                logger.warning(f"Worksheet '{worksheet_name}' not found. Creating it.")
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")
            logger.info("Successfully connected to Google Sheets", sheet=worksheet_name)
            return cls(worksheet)
        except gspread.exceptions.GSpreadException as e:
            logger.error("Failed to initialize Google Sheets sink", error=e)
            raise

    def _ensure_header(self):
        try:
            if self._worksheet.get('A1') is None:
                self._worksheet.append_row(self.HEADER)
                logger.info("Created header row in Google Sheet.", sheet=self._worksheet.title)
        except gspread.exceptions.GSpreadException as e:
            logger.error("Failed to ensure header in Google Sheet", error=e)

    def _format_rows(self, opportunities: List[MessageOpportunity]) -> List[List[str]]:
        """
        Перетворює об'єкти Opportunity у рядки для запису, використовуючи наші "перекладачі".
        """
        rows = []
        for opp in opportunities:
            msg = opp.message
            val = opp.validation

            # --- ✅ Використовуємо словники для отримання гарних назв ---
            status_str = self.STATUS_MAP.get(val.status, val.status.name)
            score_str = f"{val.score:.0%}"  # Форматуємо у відсотки, напр. "90%"
            lead_type_str = self.LEAD_TYPE_MAP.get(val.lead_type, val.lead_type) if val.lead_type else "N/A"

            rows.append([
                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                msg.guild_name or "N/A",
                msg.channel_name,
                msg.author_name,
                msg.content,
                status_str,  # <- Гарний статус
                score_str,  # <- Оцінка у відсотках
                lead_type_str,  # <- Гарний тип ліда
                msg.jump_url,
            ])
        return rows

    async def save(self, opportunities: List[MessageOpportunity]) -> None:
        if not opportunities:
            return
        rows_to_append = self._format_rows(opportunities)
        try:
            self._worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            logger.debug(f"Successfully saved {len(rows_to_append)} opps to Google Sheets.",
                         sheet=self._worksheet.title)
        except gspread.exceptions.GSpreadException as e:
            logger.error("Failed to save data to Google Sheets", error=e)