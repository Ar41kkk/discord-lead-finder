# src/dashboard/pages/tab_keyword_analysis.py

import streamlit as st
import pandas as pd
from ..constants import AI_QUALIFIED_STATUSES  # <-- Новий імпорт
from ..plotting import create_bar_chart  # <-- Новий імпорт


def display_tab(df):
    """Відображає вкладку аналізу ефективності ключових слів."""
    st.header("🔑 Аналіз Ефективності Ключових Слів")

    if 'keyword_trigger' not in df.columns:
        st.warning("У даних відсутня колонка 'keyword_trigger'.")
        return

    keyword_df = df.dropna(subset=['keyword_trigger']).copy()
    if keyword_df.empty:
        st.info("Не знайдено можливостей зі спрацюванням по ключовому слову.")
        return

    keyword_stats = keyword_df.groupby('keyword_trigger').agg(
        mentions=('keyword_trigger', 'count'),
        ai_qualified=('ai_status', lambda x: x.isin(AI_QUALIFIED_STATUSES).sum())
    ).reset_index()

    keyword_stats['conversion_rate'] = (keyword_stats['ai_qualified'] / keyword_stats['mentions']) * 100
    keyword_stats = keyword_stats.sort_values(by='ai_qualified', ascending=False)

    col1, col2 = st.columns([2, 3])
    with col1:
        st.subheader("Найефективніші ключові слова")
        # Передаємо DataFrame в нашу нову функцію
        create_bar_chart(keyword_stats.nlargest(15, 'ai_qualified'), x_col='ai_qualified',
                         y_col='keyword_trigger', title="Топ-15 слів за к-стю лідів",
                         x_label="К-сть кваліфікованих лідів", y_label="Ключове слово")

    with col2:
        st.subheader("Детальна статистика")
        st.dataframe(keyword_stats, column_config={
            "keyword_trigger": "Ключове слово", "mentions": "Кількість згадок",
            "ai_qualified": "Кваліфіковано AI", "conversion_rate": st.column_config.ProgressColumn(
                "Конверсія, %", format="%.1f%%", min_value=0, max_value=100,
            )},
                     use_container_width=True, hide_index=True, height=500)