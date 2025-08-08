# src/dashboard/pages/tab_lead_funnel.py

import streamlit as st
from ..constants import AI_QUALIFIED_STATUSES, MANUAL_APPROVED_STATUS


def display_tab(df):
    """Відображає вкладку аналізу воронки лідів у вигляді покрокових метрик."""
    st.header("🎯 Аналіз Воронки Лідів")

    if df.empty:
        st.info("Немає даних для аналізу за обраний період.")
        return

    # --- 1. Розраховуємо дані для кожного етапу воронки ---

    # Етап 1: Повідомлення, що містять ключові слова
    triggered_df = df[df['keyword_trigger'].notna()].copy()
    triggered_count = len(triggered_df)

    # Етап 2: Пройшли перший етап AI (не відсіяні як "JUNK")
    if not triggered_df.empty:
        passed_s1_df = triggered_df[triggered_df['ai_stage_one_status'] != 'UNRELEVANT']
        passed_s1_count = len(passed_s1_df)
    else:
        passed_s1_df = triggered_df
        passed_s1_count = 0

    # Етап 3: Кваліфіковані другим етапом AI
    if not passed_s1_df.empty:
        passed_s2_df = passed_s1_df[passed_s1_df['ai_stage_two_status'].isin(AI_QUALIFIED_STATUSES)]
        passed_s2_count = len(passed_s2_df)
    else:
        passed_s2_df = passed_s1_df
        passed_s2_count = 0

    # Етап 4: Підтверджено вручну
    if not passed_s2_df.empty:
        manual_approved_count = len(passed_s2_df[passed_s2_df['manual_status'] == MANUAL_APPROVED_STATUS])
    else:
        manual_approved_count = 0

    # --- 2. Розраховуємо показники конверсії між етапами ---

    conv_s1 = (passed_s1_count / triggered_count * 100) if triggered_count > 0 else 0
    conv_s2 = (passed_s2_count / passed_s1_count * 100) if passed_s1_count > 0 else 0
    conv_manual = (manual_approved_count / passed_s2_count * 100) if passed_s2_count > 0 else 0

    # --- 3. Відображаємо нову воронку у вигляді колонок ---

    st.subheader("Покрокова Воронка Конверсії")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="1. Спрацювало за ключем",
            value=triggered_count
        )

    with col2:
        st.metric(
            label="2. Пройшли AI Фільтр (Етап 1)",
            value=passed_s1_count,
            delta=f"{conv_s1:.1f}% проходять",
            help="Відсоток повідомлень, які не були відсіяні першим етапом AI як 'JUNK'."
        )

    with col3:
        st.metric(
            label="3. Кваліфіковано AI (Етап 2)",
            value=passed_s2_count,
            delta=f"{conv_s2:.1f}% проходять",
            help="Відсоток лідів, які після глибокого аналізу були визнані якісними."
        )

    with col4:
        st.metric(
            label="4. Підтверджено Вручну",
            value=manual_approved_count,
            delta=f"{conv_manual:.1f}% проходять",
            help="Відсоток якісних AI-лідів, які ви підтвердили."
        )