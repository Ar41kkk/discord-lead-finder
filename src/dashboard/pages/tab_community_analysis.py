# src/dashboard/pages/tab_community_analysis.py

import streamlit as st
from ..constants import AI_QUALIFIED_STATUSES # <-- Новий імпорт
from ..plotting import create_bar_chart # <-- Новий імпорт

def display_tab(df):
    """Відображає вкладку аналізу спільноти та користувачів."""
    st.header("👨‍👩‍👧‍👦 Аналіз Спільноти та Джерел")

    qualified_df = df[df['ai_status'].isin(AI_QUALIFIED_STATUSES)].copy()
    if qualified_df.empty:
        st.info("Не знайдено кваліфікованих лідів за обраний період.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Топ Сервери")
        create_bar_chart(qualified_df, x_col='count', y_col='server_name', title="Топ-10 серверів",
                         x_label="К-сть лідів", y_label="Сервер")
    with col2:
        st.subheader("Топ Канали")
        qualified_df['full_channel_name'] = qualified_df['server_name'] + " > " + qualified_df['channel_name']
        create_bar_chart(qualified_df, x_col='count', y_col='full_channel_name', title="Топ-10 каналів",
                         x_label="К-сть лідів", y_label="Канал")
    with col3:
        st.subheader("Топ Постачальники Лідів")
        create_bar_chart(qualified_df, x_col='count', y_col='author_name', title="Топ-10 користувачів",
                         x_label="К-сть лідів", y_label="Автор")