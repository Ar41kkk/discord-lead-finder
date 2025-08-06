# src/dkh/infrastructure/sinks/google_sheet.py
import gspread
import structlog
from typing import List

from dkh.config import settings
from dkh.domain.models import MessageOpportunity
from dkh.domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class GoogleSheetSink(OpportunitySink):
    """
    Реалізація 'приймача' даних, що записує можливості в Google Sheets.
    Форматує дані у зрозумілий для людини вигляд.
    """

    def __init__(self, worksheet: gspread.Worksheet):
        self._worksheet = worksheet
        self._ensure_header()

    @classmethod
    def create(cls, worksheet_name: str) -> "GoogleSheetSink":
        """
        Створює та повертає екземпляр GoogleSheetSink.
        Інкапсулює логіку підключення та створення аркуша.
        """
        log = logger.bind(worksheet=worksheet_name)
        log.info("Initializing Google Sheet sink...")

        config = settings.google_sheet

        try:
            gc = gspread.service_account(filename=str(config.credentials_path))
            spreadsheet = gc.open_by_key(config.spreadsheet_id)

            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
                log.info("Successfully connected to existing Google Sheet.")
            except gspread.WorksheetNotFound:
                log.warning("Worksheet not found, creating it.")
                header = settings.export.default_header
                worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols=len(header))
                worksheet.append_row(header, value_input_option='USER_ENTERED')
                log.info("Created new worksheet with header.")

            return cls(worksheet)
        except Exception:
            log.exception("Failed to initialize Google Sheets sink.")
            raise

    def _ensure_header(self):
        """Перевіряє наявність заголовка в аркуші та створює його, якщо потрібно."""
        log = logger.bind(worksheet=self._worksheet.title)
        try:
            if not self._worksheet.get('A1:A1'):
                header = settings.export.default_header
                self._worksheet.append_row(header, value_input_option='USER_ENTERED')
                log.info("Created header row in empty Google Sheet.")
        except Exception:
            log.exception("Failed to ensure header in Google Sheet.")

    def _format_rows(self, opportunities: List[MessageOpportunity]) -> List[List[str]]:
        """
        Перетворює об'єкти Opportunity у рядки для запису, використовуючи "перекладачі" з налаштувань.
        """
        rows = []
        status_map = settings.export.status_map
        lead_type_map = settings.export.lead_type_map

        for opp in opportunities:
            msg = opp.message
            val = opp.validation

            status_str = status_map.get(val.status.name, val.status.value)
            score_str = f"{val.score:.0%}" if val.score is not None else ""
            lead_type_str = lead_type_map.get(val.lead_type, val.lead_type) if val.lead_type else "N/A"

            rows.append([
                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                msg.guild_name or "N/A",
                msg.channel_name,
                msg.author_name,
                msg.content,
                status_str,
                score_str,
                lead_type_str,
                msg.jump_url,
            ])
        return rows

    async def save(self, opportunities: List[MessageOpportunity]) -> None:
        """Зберігає пакет можливостей у Google Sheet."""
        if not opportunities:
            return

        log = logger.bind(worksheet=self._worksheet.title, batch_size=len(opportunities))
        log.debug("Formatting rows for Google Sheet...")

        try:
            rows_to_append = self._format_rows(opportunities)
            log.info("Saving rows to Google Sheet...")
            self._worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            log.info("Successfully saved rows to Google Sheet.")
        except Exception:
            log.exception("Failed to save data to Google Sheets")
            raise

