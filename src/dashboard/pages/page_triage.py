# src/dashboard/pages/page_triage.py

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from .triage_views import view_deck, view_list
from ..constants import AI_QUALIFIED_STATUSES  # ← лишаємо тільки цю константу
import pandas as pd

def display_page(df):
    """Головна сторінка для сортування, роутер між режимами, з фільтром Stage1/Stage2."""

    st_autorefresh(interval=30_000, key="triage_reloader")
    st.header("📬 Сортування Нових Лідів", divider='rainbow')

    # Ініціалізуємо стан
    if 'triage_mode' not in st.session_state:
        st.session_state.triage_mode = "🗂️ Колода"
    if 'triage_stage' not in st.session_state:
        st.session_state.triage_stage = "Етап 2"

    # Нерозглянуті (manual_status == 'n/a', нечутливо до регістру)
    manual = df.get('manual_status', pd.Series(dtype=str)).astype(str).str.lower()
    unreviewed_all = df[manual.eq('n/a')].copy()

    # Радіо-перемикач етапів
    st.radio(
        "Показувати ліди, що пройшли:",
        ["Етап 1", "Етап 2"],
        key="triage_stage",
        horizontal=True
    )

    # Маска для Stage 1: усе, що НЕ 'UNRELEVANT' (як у твоїй воронці)
    if 'ai_stage_one_status' in unreviewed_all.columns:
        s1_series = unreviewed_all['ai_stage_one_status'].astype(str).str.upper()
        s1_mask = s1_series.ne('UNRELEVANT')
    else:
        # Якщо колонки нема, підстрахуємось: вважати Stage1 пройденим якщо є keyword_trigger
        s1_mask = unreviewed_all.get('keyword_trigger', pd.Series(index=unreviewed_all.index)).notna()

    # Маска для Stage 2: статус ∈ AI_QUALIFIED_STATUSES
    if 'ai_stage_two_status' in unreviewed_all.columns:
        s2_mask = unreviewed_all['ai_stage_two_status'].isin(AI_QUALIFIED_STATUSES)
    else:
        # Якщо колонки нема — Stage2 ніхто не пройшов
        s2_mask = pd.Series(False, index=unreviewed_all.index)

    # Застосовуємо вибір етапу
    if st.session_state.triage_stage == "Етап 1":
        unreviewed = unreviewed_all[s1_mask]
    else:
        unreviewed = unreviewed_all[s2_mask]

    # --- Сортування: message_timestamp → created_at → id ---
    sort_done = False
    if 'message_timestamp' in unreviewed.columns:
        ts = pd.to_datetime(unreviewed['message_timestamp'], errors='coerce', utc=True)
        unreviewed = unreviewed.assign(_ts=ts).sort_values('_ts', ascending=False).drop(columns=['_ts'])
        sort_done = True
    elif 'created_at' in unreviewed.columns:
        ts = pd.to_datetime(unreviewed['created_at'], errors='coerce', utc=True)
        unreviewed = unreviewed.assign(_ts=ts).sort_values('_ts', ascending=False).drop(columns=['_ts'])
        sort_done = True
    elif 'id' in unreviewed.columns:
        unreviewed = unreviewed.sort_values('id', ascending=False)
        sort_done = True

    if not sort_done:
        st.warning("⚠️ Не знайдено колонок для сортування ('message_timestamp' / 'created_at' / 'id'). Показуємо як є.")

    # Порожні стани
    if unreviewed.empty:
        st.info("За обраний етап немає нерозглянутих лідів.")
        return

    # Прогрес: total залежить від вибраного етапу
    if st.session_state.triage_stage == "Етап 1":
        total = len(unreviewed_all[s1_mask])
    else:
        total = len(unreviewed_all[s2_mask])

    left = len(unreviewed)  # залишок у поточному етапі
    done = max(0, total - left)
    percent = (done / total) if total else 0.0
    st.progress(percent, text=f"Відсортовано {done} з {total} (залишилось {left})")

    # Режим відображення
    st.radio(
        "Режим сортування:",
        ["🗂️ Колода", "📋 Список"],
        key='triage_mode',
        horizontal=True,
        label_visibility="collapsed"
    )

    # Рендер
    if st.session_state.triage_mode == "🗂️ Колода":
        view_deck.display_view(unreviewed)
    else:
        view_list.display_view(unreviewed)
