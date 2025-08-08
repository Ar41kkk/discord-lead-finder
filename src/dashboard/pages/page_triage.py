# src/dashboard/pages/page_triage.py

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from .triage_views import view_deck, view_list
from ..constants import AI_QUALIFIED_STATUSES

def display_page(df):
    """Головна сторінка для сортування, яка виступає в ролі роутера."""

    # Автооновлення кожні 30 с
    st_autorefresh(interval=30_000, key="triage_reloader")
    st.header("📬 Сортування Нових Лідів", divider='rainbow')

    # Ініціалізуємо стан
    if 'triage_mode' not in st.session_state:
        st.session_state.triage_mode = "🗂️ Колода"
    if 'show_only_qualified' not in st.session_state:
        st.session_state.show_only_qualified = False

    # Відфільтруємо нерозглянуті ліди
    unreviewed_all = df[df['manual_status'] == 'n/a']

    st.toggle(
        "Показувати лише якісні ліди (AI, Етап 2)",
        key='show_only_qualified',
        help="Показує лише ліди зі статусом RELEVANT або POSSIBLY_RELEVANT"
    )

    if st.session_state.show_only_qualified:
        unreviewed = unreviewed_all[
            unreviewed_all['ai_stage_two_status'].isin(AI_QUALIFIED_STATUSES)
        ]
    else:
        unreviewed = unreviewed_all

    unreviewed = unreviewed.sort_values('message_timestamp', ascending=False)

    # Якщо нічого не лишилося
    if unreviewed.empty:
        if st.session_state.show_only_qualified and not unreviewed_all.empty:
            st.info("Не знайдено якісних лідів. Вимкніть фільтр.")
        else:
            st.success("🎉 Всі ліди відсортовано!")
        return

    # Прогрес
    total   = len(df)
    left    = len(unreviewed)
    done    = total - len(unreviewed_all)
    percent = (done / total) if total else 0
    st.progress(percent, text=f"Відсортовано {done} з {total} (залишилось {left})")

    # Вибір режиму
    st.radio(
        "Режим сортування:",
        ["🗂️ Колода", "📋 Список"],
        key='triage_mode',
        horizontal=True,
        label_visibility="collapsed"
    )

    # Рендеримо відповідне view без передачі шляху до БД
    if st.session_state.triage_mode == "🗂️ Колода":
        view_deck.display_view(unreviewed)
    else:
        view_list.display_view(unreviewed)
