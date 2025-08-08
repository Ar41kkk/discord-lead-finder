# src/infrastructure/sinks/google_sheet.py
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
    # --- ОНОВЛЕНИЙ ЗАГОЛОВОК З НОВИМ ПОРЯДКОМ ---
    HEADER = [
        "Discovered By", "Time", "Server Name", "Channel Name", "Sender Name",
        "Message Content", "S1 Verdict", "S1 Score", "S2 Verdict", "S2 Score",
        "Lead Type", "Message Link"
    ]

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
            # Перевіряємо, чи заголовок відповідає новому формату. Якщо ні - оновлюємо.
            header_row = self._worksheet.get('A1:L1') # Читаємо перші 12 колонок
            if not header_row or header_row[0] != self.HEADER:
                self._worksheet.clear()
                self._worksheet.append_row(self.HEADER)
                logger.info("Created or updated header row in Google Sheet.", sheet=self._worksheet.title)
        except gspread.exceptions.GSpreadException as e:
            logger.error("Failed to ensure header in Google Sheet", error=e)

    def _format_rows(self, opportunities: List[MessageOpportunity]) -> List[List[str]]:
        """
        Перетворює об'єкти Opportunity у рядки для запису, враховуючи двохетапну валідацію.
        """
        rows = []
        for opp in opportunities:
            msg = opp.message
            s1_val = opp.stage_one_validation
            s2_val = opp.stage_two_validation

            s1_status_str = self.STATUS_MAP.get(s1_val.status, s1_val.status.name)
            s1_score_str = f"{s1_val.score:.0%}"

            if s2_val:
                s2_status_str = self.STATUS_MAP.get(s2_val.status, s2_val.status.name)
                s2_score_str = f"{s2_val.score:.0%}"
                lead_type_str = self.LEAD_TYPE_MAP.get(s2_val.lead_type, s2_val.lead_type) if s2_val.lead_type else "N/A"
            else:
                s2_status_str, s2_score_str, lead_type_str = "N/A", "N/A", "N/A"

            # --- ОНОВЛЕНИЙ ПОРЯДОК ДАНИХ У РЯДКУ ---
            rows.append([
                opp.bot_name or "N/A",  # <-- Ім'я акаунта тепер на першому місці
                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                msg.guild_name or "N/A",
                msg.channel_name,
                msg.author_name,
                msg.content,
                s1_status_str,
                s1_score_str,
                s2_status_str,
                s2_score_str,
                lead_type_str,
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