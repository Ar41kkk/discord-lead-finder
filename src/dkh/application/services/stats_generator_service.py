# src/dkh/application/services/stats_generator_service.py
from collections import defaultdict
import gspread
import structlog

from dkh.config import settings
from dkh.database.models import Opportunity, ValidationStatus

logger = structlog.get_logger(__name__)


class StatsGeneratorService:
    """
    Сервіс для генерації розширеної статистики, включаючи ручну валідацію
    та розрахунок конверсій.
    """

    def __init__(self):
        self.server_stats = defaultdict(lambda: defaultdict(int))
        self.keyword_stats = defaultdict(lambda: defaultdict(int))
        self.manual_approved_status = "approved"

    async def run(self):
        """Головний метод, що запускає процес генерації статистики."""
        logger.info("Calculating extended stats from the database...")
        await self._calculate_stats_from_db()
        await self._write_stats_to_sheet()
        logger.info("Extended stats generation and upload complete.")

    def _safe_division(self, numerator, denominator):
        """Допоміжна функція для безпечного ділення, щоб уникнути помилок ділення на нуль."""
        return numerator / denominator if denominator else 0

    async def _calculate_stats_from_db(self):
        """
        Витягує всі записи з БД та агрегує розширену статистику.
        """
        logger.info("Fetching all opportunities from the database...")
        opportunities = await Opportunity.all()
        logger.info(f"Found {len(opportunities)} total records to process.")

        if not opportunities:
            logger.warning("No opportunities found in the database. Nothing to process.")
            return

        for op in opportunities:
            # --- Статистика по серверах ---
            if op.server_name:
                stats = self.server_stats[op.server_name]
                stats['keyword_hits'] += 1
                if op.ai_status in [ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE]:
                    stats['openai_approved'] += 1
                if op.manual_status and op.manual_status.lower() == self.manual_approved_status:
                    stats['manual_approved'] += 1

            # --- Статистика по ключових словах ---
            if op.keyword_trigger:
                stats = self.keyword_stats[op.keyword_trigger]
                stats['mentions'] += 1
                if op.ai_status in [ValidationStatus.RELEVANT, ValidationStatus.HIGH_MAYBE]:
                    stats['openai_approved'] += 1
                if op.manual_status and op.manual_status.lower() == self.manual_approved_status:
                    stats['manual_approved'] += 1

        logger.info("Extended stats calculation complete.")

    async def _write_stats_to_sheet(self):
        """
        Форматує та записує розширену статистику в Google Sheets.
        """
        if not self.server_stats and not self.keyword_stats:
            logger.warning("No stats were calculated, skipping Google Sheet update.")
            return

        logger.info("Writing extended stats to Google Sheet...")
        try:
            # --- ✅ ОНОВЛЕНА ЛОГІКА ТУТ ---

            # --- Блок 1: Проста статистика по серверах (як на скріншоті) ---
            server_data_simple = []
            for name, data in sorted(self.server_stats.items()):
                server_data_simple.append([
                    name,
                    data.get('keyword_hits', 0),
                    data.get('openai_approved', 0)
                ])

            # --- Блок 2: Проста статистика по ключових словах (як на скріншоті) ---
            keyword_data_simple = []
            for name, data in sorted(self.keyword_stats.items()):
                keyword_data_simple.append([
                    name,
                    data.get('mentions', 0),
                    data.get('openai_approved', 0)
                ])

            # --- Блок 3: Детальна статистика по ключових словах (нова) ---
            keyword_data_detailed = []
            for name, data in sorted(self.keyword_stats.items()):
                mentions = data.get('mentions', 0)
                openai_app = data.get('openai_approved', 0)
                manual_app = data.get('manual_approved', 0)
                kw_openai_perc = self._safe_division(openai_app, mentions)
                openai_manual_perc = self._safe_division(manual_app, openai_app)
                keyword_data_detailed.append([
                    name,  # Keyword
                    f"{kw_openai_perc:.1%}",  # Keyword/OpenAI Perc.
                    openai_app,  # OpenAI Number
                    f"{openai_manual_perc:.1%}",  # OpenAI/Manual Perc.
                    manual_app  # Manual
                ])

            # --- Формуємо фінальну таблицю ---
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

            # --- Записуємо в Google Sheet ---
            config = settings.google_sheet
            gc = gspread.service_account(filename=str(config.credentials_path))
            spreadsheet = gc.open_by_key(config.spreadsheet_id)
            worksheet_name = config.stats_sheet_name

            try:
                stats_sheet = spreadsheet.worksheet(worksheet_name)
                stats_sheet.clear()
            except gspread.WorksheetNotFound:
                stats_sheet = spreadsheet.add_worksheet(title=worksheet_name, rows="1000", cols=len(final_rows[0]))

            stats_sheet.update(final_rows, 'A1')
            logger.info("Successfully wrote extended stats to sheet.", sheet_name=worksheet_name)

        except Exception:
            logger.exception("Failed to write extended stats to Google Sheet.")
