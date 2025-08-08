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

    # Використовуємо st.data_editor для можливості редагування в майбутньому
    st.dataframe(
        approved_df[[
            'message_timestamp', 'server_name', 'channel_name', 'author_name',
            'ai_status', 'ai_score', 'manual_status', 'message_content', 'message_url'
        ]],
        use_container_width=True, height=600, hide_index=True
    )