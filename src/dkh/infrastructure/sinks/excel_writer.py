from pathlib import Path
from typing import List

import openpyxl
import structlog

from dkh.domain.models import MessageOpportunity
from dkh.domain.ports import OpportunitySink

logger = structlog.get_logger(__name__)


class ExcelSink(OpportunitySink):
    """
    Реалізація 'приймача' даних, що записує можливості у локальний Excel файл.
    """

    HEADER = ['Timestamp', 'Status', 'Score', 'Guild', 'Channel', 'Author', 'Content', 'URL']

    def __init__(self, filepath: Path):
        self._filepath = filepath
        self._ensure_file_and_header()

    def _ensure_file_and_header(self):
        """Створює файл та заголовок, якщо вони не існують."""
        if not self._filepath.exists():
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.append(self.HEADER)
            workbook.save(self._filepath)
            logger.info(f'Created new Excel file at {self._filepath}')

    def _format_rows(self, opportunities: List[MessageOpportunity]) -> List[List[str]]:
        """Перетворює список об'єктів MessageOpportunity у формат для запису."""
        # Ця функція ідентична тій, що в GoogleSheetSink
        rows = []
        for opp in opportunities:
            msg = opp.message
            val = opp.validation
            rows.append(
                [
                    msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    val.status.name,
                    f'{val.score:.2f}',
                    msg.guild_name or 'N/A',
                    msg.channel_name,
                    msg.author_name,
                    msg.content,
                    msg.jump_url,
                ]
            )
        return rows

    async def save(self, opportunities: List[MessageOpportunity]) -> None:
        if not opportunities:
            return

        rows_to_append = self._format_rows(opportunities)
        try:
            workbook = openpyxl.load_workbook(self._filepath)
            sheet = workbook.active
            for row in rows_to_append:
                sheet.append(row)
            workbook.save(self._filepath)
            # ✅ CHANGE THIS LINE FROM .info to .debug
            logger.debug(f"Successfully saved {len(rows_to_append)} opportunities to Excel.")
        except (IOError, openpyxl.utils.exceptions.InvalidFileException) as e:
            logger.error("Failed to save data to Excel file", filepath=self._filepath, error=e)