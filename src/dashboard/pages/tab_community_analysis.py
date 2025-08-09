import streamlit as st
import pandas as pd
from ..constants import AI_QUALIFIED_STATUSES

def display_tab(df: pd.DataFrame):
    """Аналіз спільноти з захистом від відсутніх колонок."""
    st.header("👨‍👩‍👧‍👦 Аналіз Спільноти")

    if df is None or df.empty:
        st.info("Немає даних для аналізу.")
        return

    # Безпечний доступ до колонки Stage 2
    s2 = df.get("ai_stage_two_status")
    if s2 is None:
        st.warning("Відсутня колонка 'ai_stage_two_status' у даних.")
        return

    s2 = s2.astype(str).fillna("N/A")
    qualified_df = df[s2.isin(AI_QUALIFIED_STATUSES)].copy()
    if qualified_df.empty:
        st.info("Не знайдено кваліфікованих лідів за обраний період.")
        return

    # далі — твоя логіка табу (топ серверів/каналів/авторів і т.д.)
    # приклад:
    st.subheader("Топ серверів (за кількістю кваліфікованих лідів)")
    top_servers = qualified_df["server_name"].value_counts().head(10).reset_index()
    top_servers.columns = ["server_name", "count"]
    st.dataframe(top_servers, use_container_width=True, hide_index=True)
