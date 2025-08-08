# src/dashboard/pages/tab_approved_leads.py

import streamlit as st
from ..constants import MANUAL_APPROVED_STATUS


def display_tab(df):
    """Відображає відфільтрований список схвалених лідів."""
    st.header("✅ Схвалені Ліди")

    approved_df = df[df['manual_status'] == MANUAL_APPROVED_STATUS].copy()

    if approved_df.empty:
        st.info("Ще немає схвалених лідів за обраний період.")
        return

    st.markdown(f"Знайдено **{len(approved_df)}** схвалених лідів.")

    # --- ОНОВЛЕНІ КОЛОНКИ ---
    st.dataframe(
        approved_df[[
            'message_timestamp', 'server_name', 'channel_name', 'author_name', 'bot_user_name',
            'ai_stage_one_status', 'ai_stage_two_status', 'ai_stage_two_score',
            'manual_status', 'message_content', 'message_url'
        ]],  # <-- Додано 'bot_user_name'
        use_container_width=True, height=600, hide_index=True
    )