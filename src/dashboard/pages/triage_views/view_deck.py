# src/dashboard/pages/triage_views/view_deck.py

import streamlit as st
import pandas as pd
import time
from ...db_utils import update_opportunity_status


def display_view(df, db_path):
    """Відображає режим сортування 'Колода'."""

    # --- Функції-обробники ---
    def handle_action(status, opp_id):
        st.session_state.last_action = {"id": opp_id, "previous_status": "n/a", "timestamp": time.time()}
        if update_opportunity_status(db_path, opp_id, status):
            st.toast(f"Лід #{opp_id} позначено як '{status}'!", icon="✅")
            st.cache_data.clear()
        else:
            st.toast(f"Помилка при оновленні статусу ліда #{opp_id}.", icon="❌")

    def handle_undo(db_path):
        last_action = st.session_state.get('last_action')
        if last_action and update_opportunity_status(db_path, last_action["id"], last_action["previous_status"]):
            st.toast(f"Дію для ліда #{last_action['id']} скасовано.", icon="↩️")
            st.session_state.last_action = None
            st.cache_data.clear()
        else:
            st.error("Не вдалося скасувати останню дію.")

    current_lead = df.iloc[0]
    opp_id = current_lead['id']

    # --- Відображення картки ---
    with st.container(border=True):
        # ... (код картки залишається майже без змін, але тепер він ізольований)
        st.markdown(f"""...""")  # HTML for card header
        st.divider()
        col_main, col_ai = st.columns([3, 1])
        with col_main:
            st.markdown(f"**Автор:** {current_lead['author_name']}")
            st.markdown(f"**Ключове слово:** `{current_lead['keyword_trigger']}`" if pd.notna(
                current_lead['keyword_trigger']) else "")
            st.markdown(f"<blockquote>{current_lead['message_content']}</blockquote>", unsafe_allow_html=True)
            st.link_button("🔗 Перейти до повідомлення", current_lead['message_url'])
        with col_ai:
            st.metric("AI Score", f"{current_lead['ai_score']:.0%}")
            st.info(f"**Статус AI:**\n{current_lead['ai_status']}")

    st.write("")
    if st.session_state.get('last_action') and time.time() - st.session_state.last_action['timestamp'] > 10:
        st.session_state.last_action = None

    action_col1, action_col2, action_col3 = st.columns([2, 2, 3])
    with action_col1:
        st.button("❌ Reject", use_container_width=True, on_click=handle_action, args=('rejected', opp_id))
    with action_col2:
        st.button("✅ Approve", use_container_width=True, type="primary", on_click=handle_action,
                  args=('approved', opp_id))
    with action_col3:
        if st.session_state.get('last_action'):
            st.button("↩️ Скасувати останню дію", use_container_width=True, on_click=handle_undo, args=(db_path,))