# src/dashboard/pages/triage_views/view_list.py

import streamlit as st
from ...db_utils import update_opportunities_status_bulk


def display_view(df, db_path):
    """Відображає режим сортування 'Список'."""

    def handle_bulk_action(status, selected_ids):
        if not selected_ids:
            st.warning("Ви не вибрали жодного ліда.")
            return
        if update_opportunities_status_bulk(db_path, selected_ids, status):
            st.toast(f"{len(selected_ids)} лідів позначено як '{status}'!", icon="✅")
            st.cache_data.clear()
        else:
            st.toast(f"Помилка при масовому оновленні статусів.", icon="❌")

    if 'select_all' not in st.session_state:
        st.session_state.select_all = False

    df_display = df.copy()

    st.checkbox("Вибрати все", key="select_all")
    df_display['Вибрати'] = st.session_state.select_all

    st.info("Виберіть ліди за допомогою галочок, а потім застосуйте дію за допомогою кнопок нижче.")

    # --- ВИПРАВЛЕННЯ ТУТ ---
    # Створюємо нову колонку для коректного відображення прогресу
    df_display['ai_score_percent'] = df_display['ai_score'] * 100

    edited_df = st.data_editor(
        df_display[['Вибрати', 'message_content', 'ai_status', 'ai_score_percent', 'keyword_trigger', 'id']],
        key="bulk_select_editor", use_container_width=True, height=500, hide_index=True,
        column_config={
            "message_content": st.column_config.TextColumn("Повідомлення", width="large"),
            "ai_status": "Статус AI",
            "ai_score_percent": st.column_config.ProgressColumn(
                "Score AI",
                help="Впевненість AI у своєму рішенні",
                format="%d%%",  # Показуємо як ціле число з %
                min_value=0,
                max_value=100,  # Тепер max_value відповідає даним
            ),
            "keyword_trigger": "Ключове слово",
        },
        disabled=['message_content', 'ai_status', 'ai_score_percent', 'keyword_trigger', 'id']
    )

    selected_rows = edited_df[edited_df['Вибрати']]
    selected_ids = selected_rows['id'].tolist()

    st.markdown(f"**Вибрано: {len(selected_ids)}**")

    btn_col1, btn_col2, _ = st.columns([2, 2, 4])
    with btn_col1:
        st.button("❌ Відхилити вибрані", use_container_width=True, on_click=handle_bulk_action,
                  args=('rejected', selected_ids))
    with btn_col2:
        st.button("✅ Схвалити вибрані", use_container_width=True, type="primary", on_click=handle_bulk_action,
                  args=('approved', selected_ids))
