# src/dashboard/pages/page_triage.py

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from .triage_views import view_deck, view_list
from ..constants import AI_QUALIFIED_STATUSES  # <-- Новий імпорт


def display_page(df, db_path):
    """Головна сторінка для сортування, яка виступає в ролі роутера."""

    st_autorefresh(interval=30000, key="triage_reloader")
    st.header("📬 Сортування Нових Лідів", divider='rainbow')

    # Ініціалізація стану в сесії
    if 'triage_mode' not in st.session_state:
        st.session_state.triage_mode = "🗂️ Колода"
    if 'last_action' not in st.session_state:
        st.session_state.last_action = None
    if 'show_only_qualified' not in st.session_state:
        st.session_state.show_only_qualified = False  # Стан для нового тоглера

    unreviewed_df_all = df[df['manual_status'] == 'n/a'].copy()

    # --- НОВИЙ ФІЛЬТР-ТОГЛЕР ---
    st.toggle(
        "Показувати лише якісні ліди (AI)",
        key='show_only_qualified',
        help="Показує лише ліди зі статусом RELEVANT або POSSIBLY_RELEVANT."
    )

    if st.session_state.show_only_qualified:
        unreviewed_df = unreviewed_df_all[unreviewed_df_all['ai_status'].isin(AI_QUALIFIED_STATUSES)]
    else:
        unreviewed_df = unreviewed_df_all

    unreviewed_df = unreviewed_df.sort_values(by='message_timestamp', ascending=False)

    if unreviewed_df.empty:
        if st.session_state.show_only_qualified and not unreviewed_df_all.empty:
            st.info("Не знайдено якісних лідів для сортування. Вимкніть фільтр, щоб побачити всі.")
        else:
            st.success("🎉 Всі ліди відсортовано! Очікуємо на нові...")

        if st.session_state.get('last_action'):
            # ... (можна додати кнопку скасування, якщо потрібно)
            pass
        return

    # Прогрес-бар та інша спільна інформація
    total_unreviewed = len(unreviewed_df)
    total_leads = len(df)
    reviewed_leads = total_leads - len(unreviewed_df_all)
    progress_percent = (reviewed_leads / total_leads) * 100 if total_leads > 0 else 0
    st.progress(progress_percent / 100,
                text=f"Відсортовано {reviewed_leads} з {total_leads} лідів ({total_unreviewed} залишилось показати)")

    # Радіо-кнопки для вибору режиму, що зберігають свій стан
    st.radio(
        "Оберіть режим сортування:",
        ["🗂️ Колода", "📋 Список"],
        key='triage_mode',  # Зберігаємо вибір в session_state
        horizontal=True,
        label_visibility="collapsed"
    )

    # Відображаємо обраний режим
    if st.session_state.triage_mode == "🗂️ Колода":
        view_deck.display_view(unreviewed_df, db_path)

    elif st.session_state.triage_mode == "📋 Список":
        view_list.display_view(unreviewed_df, db_path)
