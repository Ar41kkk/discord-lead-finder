# src/dkh/application/services/stats_generator_service.py
from collections import defaultdict
import gspread
import structlog
from typing import List, Any

from config import settings
from database.models import Opportunity, ValidationStatus

logger = structlog.get_logger(__name__)


class StatsGeneratorService:
    """
    Сервіс для генерації розширеної статистики, включаючи ручну валідацію
    та розрахунок конверсій.
    """
    # ✅ Виносимо константу для легкого доступу та зміни
    MANUAL_APPROVED_STATUS = "approved"

    def __init__(self):
        self.server_stats = defaultdict(lambda: defaultdict(int))
        self.keyword_stats = defaultdict(lambda: defaultdict(int))

    async def run(self):
        """Головний метод, що запускає процес генерації статистики."""
        logger.info("Starting stats generation process...")
        try:
            await self._calculate_stats_from_db()
            await self._write_stats_to_sheet()
            logger.info("✅ Stats generation and upload completed successfully.")
        except Exception:
            logger.exception("Stats generation process failed.")

    def _safe_division(self, numerator, denominator):
        """Допоміжна функція для безпечного ділення."""
        return numerator / denominator if denominator else 0

    async def _calculate_stats_from_db(self):
        """Витягує всі записи з БД та агрегує розширену статистику."""
        logger.info("Fetching all opportunities from the database...")
        opportunities = await Opportunity.all()

        if not opportunities:
            logger.warning("No opportunities found in the database. Nothing to process.")
            return

        log = logger.bind(total_records=len(opportunities))
        log.info("Starting stats calculation...")

        for op in opportunities:
            # --- Статистика по серверах ---
            if op.server_name:
                stats = self.server_stats[op.server_name]
                stats['keyword_hits'] += 1
                # Виправляємо неіснуючий статус на правильний з доменної моделі
                if op.ai_status in {ValidationStatus.RELEVANT, ValidationStatus.POSSIBLY_RELEVANT}:
                    stats['openai_approved'] += 1
                if op.manual_status and op.manual_status.lower() == self.MANUAL_APPROVED_STATUS:
                    stats['manual_approved'] += 1

            # --- Статистика по ключових словах ---
            if op.keyword_trigger:
                stats = self.keyword_stats[op.keyword_trigger]
                stats['mentions'] += 1
                # І тут також
                if op.ai_status in {ValidationStatus.RELEVANT, ValidationStatus.POSSIBLY_RELEVANT}:
                    stats['openai_approved'] += 1
                if op.manual_status and op.manual_status.lower() == self.MANUAL_APPROVED_STATUS:
                    stats['manual_approved'] += 1

        log.info("Finished calculating stats.")

    def _prepare_final_rows(self) -> List[List[Any]]:
        """Готує дані для запису в таблицю, комбінуючи різні блоки статистики."""
        # Блок 1: Проста статистика по серверах
        server_data_simple = [[name, data.get('keyword_hits', 0), data.get('openai_approved', 0)]
                              for name, data in sorted(self.server_stats.items())]

        # Блок 2: Проста статистика по ключових словах
        keyword_data_simple = [[name, data.get('mentions', 0), data.get('openai_approved', 0)]
                               for name, data in sorted(self.keyword_stats.items())]

        # Блок 3: Детальна статистика по ключових словах
        keyword_data_detailed = []
        for name, data in sorted(self.keyword_stats.items()):
            mentions = data.get('mentions', 0)
            openai_app = data.get('openai_approved', 0)
            manual_app = data.get('manual_approved', 0)
            kw_openai_perc = self._safe_division(openai_app, mentions)
            openai_manual_perc = self._safe_division(manual_app, openai_app)
            keyword_data_detailed.append([
                name, f"{kw_openai_perc:.1%}", openai_app,
                f"{openai_manual_perc:.1%}", manual_app
            ])

        # Формуємо фінальну таблицю
        header1 = ["Server Name", "Keyword Number", "OpenAI Number"]
        header2 = ["Keyword", "Mentions", "OpenAI Number"]
        header3 = ["Keyword", "Keyword/Openai Perc.", "OpenAI Number", "OpeAI/Manual Perc.", "Manual"]
        final_header = header1 + [""] + header2 + [""] + header3
        final_rows = [final_header]

        num_rows = max(len(server_data_simple), len(keyword_data_simple), len(keyword_data_detailed))
        for i in range(num_rows):
            row1 = server_data_simple[i] if i < len(server_data_simple) else [""] * len(header1)
            row2 = keyword_data_simple[i] if i < len(keyword_data_simple) else [""] * len(header2)
            row3 = keyword_data_detailed[i] if i < len(keyword_data_detailed) else [""] * len(header3)
            final_rows.append(row1 + [""] + row2 + [""] + row3)

        return final_rows

    async def _write_stats_to_sheet(self):
        """Форматує та записує розширену статистику в Google Sheets."""
        if not self.server_stats and not self.keyword_stats:
            logger.warning("No stats were calculated, skipping Google Sheet update.")
            return

        worksheet_name = settings.google_sheet.stats_sheet_name
        log = logger.bind(worksheet=worksheet_name)
        log.info("Writing extended stats to Google Sheet...")

        try:
            final_rows = self._prepare_final_rows()
            log.info(f"Prepared {len(final_rows)} rows for upload.")

            # Записуємо в Google Sheet
            config = settings.google_sheet
            gc = gspread.service_account(filename=str(config.credentials_path))
            spreadsheet = gc.open_by_key(config.spreadsheet_id)

            try:
                stats_sheet = spreadsheet.worksheet(worksheet_name)
                stats_sheet.clear()
            except gspread.WorksheetNotFound:
                log.warning("Worksheet not found, creating it.")
                stats_sheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols=len(final_rows[0]))

            stats_sheet.update(final_rows, 'A1', value_input_option='USER_ENTERED')
            log.info("Successfully wrote extended stats to sheet.")

        except Exception:
            log.exception("Failed to write extended stats to Google Sheet.")
            raise
