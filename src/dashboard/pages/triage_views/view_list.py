# src/dashboard/pages/triage_views/view_list.py

import streamlit as st
from config.settings import settings
from ...db_utils import update_opportunities_status_bulk
from config.settings import settings
from sqlalchemy.engine import make_url
import pandas as pd

def display_view(df: pd.DataFrame):
    """Відображає режим сортування 'Список'."""

    # Шлях до SQLite з налаштувань
    db_url = settings.database.db_url

    # Обробник масової дії
    def handle_bulk_action(status: str, selected_ids: list[int]):
        if not selected_ids:
            st.warning("Ви не вибрали жодного ліда.")
            return
        if update_opportunities_status_bulk(db_url, selected_ids, status):
            st.toast(f"{len(selected_ids)} лідів позначено як '{status}'!", icon="✅")
            st.cache_data.clear()
            st.rerun()  # ← оновлюємо одразу
        else:
            st.toast("Помилка при масовому оновленні.", icon="❌")

    # Підготовка для data_editor
    if "select_all" not in st.session_state:
        st.session_state.select_all = False

    df_disp = df.copy()
    st.checkbox("Вибрати все", key="select_all")
    df_disp["Вибрати"] = st.session_state.select_all

    df_disp["ai_stage_two_score_percent"] = df_disp["ai_stage_two_score"].fillna(0) * 100

    edited = st.data_editor(
        df_disp[[
            "Вибрати", "message_content", "bot_user_name",
            "ai_stage_one_status", "ai_stage_two_status",
            "ai_stage_two_score_percent", "keyword_trigger", "id"
        ]],
        key="bulk_select_editor",
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "message_content": st.column_config.TextColumn("Повідомлення", width="large"),
            "bot_user_name": st.column_config.TextColumn("Акаунт", width="small"),
            "ai_stage_one_status": st.column_config.TextColumn("AI Етап 1", width="medium"),
            "ai_stage_two_status": st.column_config.TextColumn("AI Етап 2", width="medium"),
            "ai_stage_two_score_percent": st.column_config.ProgressColumn(
                "Score AI (Eтап 2)",
                min_value=0, max_value=100, format="%d%%"
            ),
            "keyword_trigger": "Ключове слово",
        },
        disabled=[
            "message_content", "bot_user_name",
            "ai_stage_one_status", "ai_stage_two_status",
            "ai_stage_two_score_percent", "keyword_trigger", "id"
        ]
    )

    selected = edited[edited["Вибрати"]]
    ids = selected["id"].tolist()
    st.markdown(f"**Вибрано: {len(ids)}**")

    b1, b2, _ = st.columns([2,2,4])
    with b1:
        st.button("❌ Відхилити вибрані", use_container_width=True,
                  on_click=handle_bulk_action, args=("rejected", ids))
    with b2:
        st.button("✅ Схвалити вибрані", use_container_width=True, type="primary",
                  on_click=handle_bulk_action, args=("approved", ids))
