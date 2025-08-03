# src/dkh/application/services/analyze_stats.py
# encoding: utf-8
import json

import pandas as pd
import structlog

from dkh.config.settings import settings

logger = structlog.get_logger(__name__)


class StatsAnalyzer:
    """
    Reads the simplified stats file and generates an Excel report.
    """

    def __init__(self):
        self.stats_file = settings.log_dir / 'stats.json'
        self.output_file = settings.log_dir / 'stats_report.xlsx'
        self.target_keywords = {k.lower() for k in settings.keywords}

    def run(self) -> None:
        """Main method to load data, process it, and write the report."""
        if not self.stats_file.exists():
            logger.error('stats_file_not_found', path=self.stats_file)
            return

        df = self._load_and_prepare_dataframe()
        if df.empty:
            logger.warning('no_stats_to_analyze')
            return

        # Create summary dataframes
        keyword_summary = self._summarize_by(df, 'keyword')
        guild_summary = self._summarize_by(df, ['guild_id', 'guild_name'])

        # Write to Excel
        with pd.ExcelWriter(self.output_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Raw Stats')
            keyword_summary.to_excel(writer, index=False, sheet_name='Summary by Keyword')
            guild_summary.to_excel(writer, index=False, sheet_name='Summary by Guild')

        logger.info('stats_report_generated', path=self.output_file)

    def _load_and_prepare_dataframe(self) -> pd.DataFrame:
        """Loads the JSON stats and converts them into a clean DataFrame."""
        with open(self.stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        guild_names = data.get('guild_names', {})
        raw_stats = data.get('stats', {})

        records = []
        for key_str, stat in raw_stats.items():
            guild_id, channel_id, keyword = key_str.split('|')
            records.append(
                {
                    'guild_id': guild_id,
                    'guild_name': guild_names.get(guild_id, 'Unknown'),
                    'channel_id': channel_id,
                    'keyword': keyword,
                    'message_count': stat.get('message_count', 0),
                    'avg_score': stat.get('avg_score', 0.0),
                    'first_seen': stat.get('first_seen'),
                    'last_seen': stat.get('last_seen'),
                }
            )

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).sort_values('message_count', ascending=False)

    def _summarize_by(self, df: pd.DataFrame, group_by_cols: str | list[str]) -> pd.DataFrame:
        """Helper to create an aggregated summary, ensuring all items are present."""
        summary = (
            df.groupby(group_by_cols)['message_count']
            .sum()
            .reset_index()
            .sort_values('message_count', ascending=False)
        )
        return summary


# This allows the script to be run directly for analysis
if __name__ == '__main__':
    analyzer = StatsAnalyzer()
    analyzer.run()
