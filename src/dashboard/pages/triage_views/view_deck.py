# src/dashboard/pages/triage_views/view_deck.py

import streamlit as st
import pandas as pd
import time
from ...db_utils import update_opportunity_status
from config.settings import settings
from sqlalchemy.engine import make_url

def display_view(df: pd.DataFrame):
    """Відображає режим сортування 'Колода'."""

    # отримуємо шлях до sqlite-файлу з налаштувань
    url = make_url(settings.database.db_url)
    if url.drivername != "sqlite":
        raise RuntimeError("Підтримується лише sqlite для triage_views")
    db_path = url.database

    # Обробник однієї дії
    def handle_action(status: str, opp_id: int):
        st.session_state.last_action = {
            "id": opp_id,
            "previous_status": "n/a",
            "timestamp": time.time()
        }
        if update_opportunity_status(db_path, opp_id, status):
            st.toast(f"Лід #{opp_id} позначено як '{status}'!", icon="✅")
            st.cache_data.clear()
        else:
            st.toast(f"Помилка при оновленні ліда #{opp_id}.", icon="❌")

    # Скасування останньої дії
    def handle_undo():
        last = st.session_state.get("last_action")
        if last and update_opportunity_status(db_path, last["id"], last["previous_status"]):
            st.toast(f"Дію для ліда #{last['id']} скасовано.", icon="↩️")
            st.session_state.last_action = None
            st.cache_data.clear()
        else:
            st.error("Не вдалося скасувати останню дію.")

    # Беремо перший лід
    current = df.iloc[0]
    opp_id = current["id"]

    # Відображаємо картку
    with st.container():
        st.markdown(
            f"**Сервер:** `{current['server_name']}` | "
            f"**Канал:** `{current['channel_name']}`"
        )
        st.divider()
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"**Автор:** {current['author_name']}")
            st.markdown(f"**Акаунт:** {current['bot_user_name']}")
            if pd.notna(current["keyword_trigger"]):
                st.markdown(f"**Ключове слово:** `{current['keyword_trigger']}`")
            st.markdown(f"> {current['message_content']}")
            st.link_button("🔗 Перейти до повідомлення", current["message_url"])
        with right:
            st.metric("AI Score (Етап 2)", f"{current['ai_stage_two_score']:.0%}")
            st.info(f"**Статус AI (Етап 1):** {current['ai_stage_one_status']}")
            st.info(f"**Статус AI (Етап 2):** {current['ai_stage_two_status']}")

    # Прибираємо кнопку Undo через 10 секунд
    if st.session_state.get("last_action") and time.time() - st.session_state.last_action["timestamp"] > 10:
        st.session_state.last_action = None

    # Кнопки дій
    c1, c2, c3 = st.columns([2,2,3])
    with c1:
        st.button("❌ Reject", use_container_width=True,
                  on_click=handle_action, args=("rejected", opp_id))
    with c2:
        st.button("✅ Approve", use_container_width=True, type="primary",
                  on_click=handle_action, args=("approved", opp_id))
    with c3:
        if st.session_state.get("last_action"):
            st.button("↩️ Скасувати останню дію", use_container_width=True,
                      on_click=handle_undo)
