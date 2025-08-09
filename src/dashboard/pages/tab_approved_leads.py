# src/dashboard/pages/tab_approved_leads.py

import streamlit as st
import pandas as pd
from ..constants import MANUAL_APPROVED_STATUS

def display_tab(df: pd.DataFrame):
    """Відображає відфільтрований список схвалених лідів."""
    st.header("✅ Схвалені Ліди")

    if df.empty:
        st.info("Немає даних за обраний період.")
        return

    # на всяк випадок — уніфікуємо регістр (у load_data вже є .str.lower(), але хай буде надійніше)
    manual = df["manual_status"].astype(str).str.lower()
    approved_df = df[manual.eq(MANUAL_APPROVED_STATUS)].copy()

    if approved_df.empty:
        st.info("Ще немає схвалених лідів за обраний період.")
        return

    # фільтри (сервер / акаунт)
    colf1, colf2 = st.columns(2)
    with colf1:
        server_opt = ["Всі"] + sorted([s for s in approved_df["server_name"].dropna().unique()])
        selected_server = st.selectbox("Сервер", server_opt, index=0)
    with colf2:
        bot_opt = ["Всі"] + sorted([b for b in approved_df["bot_user_name"].dropna().unique()])
        selected_bot = st.selectbox("Акаунт бота", bot_opt, index=0)

    if selected_server != "Всі":
        approved_df = approved_df[approved_df["server_name"] == selected_server]
    if selected_bot != "Всі":
        approved_df = approved_df[approved_df["bot_user_name"] == selected_bot]

    if approved_df.empty:
        st.info("За вибраними фільтрами немає результатів.")
        return

    # сортуємо новіші зверху
    if "message_timestamp" in approved_df.columns:
        approved_df = approved_df.sort_values("message_timestamp", ascending=False)

    st.markdown(f"Знайдено **{len(approved_df)}** схвалених лідів.")

    # невеликий експорт
    csv = approved_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Експортувати CSV", csv, "approved_leads.csv", "text/csv")

    # таблиця
    show_cols = [
        'message_timestamp', 'server_name', 'channel_name', 'author_name', 'bot_user_name',
        'ai_stage_one_status', 'ai_stage_two_status', 'ai_stage_two_score',
        'manual_status', 'message_content', 'message_url'
    ]
    show_cols = [c for c in show_cols if c in approved_df.columns]  # захист від KeyError

    st.dataframe(
        approved_df[show_cols],
        use_container_width=True, height=600, hide_index=True
    )
