import streamlit as st
from ..constants import AI_QUALIFIED_STATUSES


def display_tab(df):
    """Відображає головну вкладку з ключовими показниками."""
    st.subheader("📊 Ключові Показники")

    if df.empty:
        st.info("Немає даних для відображення за обраний період.")
        return

    # --- 1. Розрахунок всіх метрик ---
    total_opportunities = len(df)
    keyword_triggers = df['keyword_trigger'].notna().sum()

    ai_qualified_df = df[df['ai_stage_two_status'].isin(AI_QUALIFIED_STATUSES)]
    ai_qualified_count = len(ai_qualified_df)

    manual_approved_count = len(df[df['manual_status'] == 'approved'])

    # Розрахунок конверсій
    keyword_conversion = (ai_qualified_count / keyword_triggers) * 100 if keyword_triggers > 0 else 0
    manual_conversion = (manual_approved_count / ai_qualified_count) * 100 if ai_qualified_count > 0 else 0

    # --- 2. Покращене відображення (UI/UX) ---
    st.markdown("##### Загальна Воронка")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всього можливостей", total_opportunities)
    col2.metric("Спрацювало за ключем", keyword_triggers)
    col3.metric("Кваліфіковано AI (Етап 2)", ai_qualified_count)
    col4.metric("Підтверджено Вручну", manual_approved_count)

    st.divider()

    st.markdown("##### Показники Ефективності")
    kpi1, kpi2 = st.columns(2)
    kpi1.metric(
        "Конверсія з Ключового Слова в AI Ліда",
        f"{keyword_conversion:.1f}%",
        help="Який відсоток повідомлень, знайдених за ключовими словами, AI вважає якісними лідами."
    )
    kpi2.metric(
        "Конверсія з AI Ліда в Підтверджені",
        f"{manual_conversion:.1f}%",
        help="Який відсоток лідів, кваліфікованих AI, ви підтвердили вручну."
    )

    st.divider()

    # --- 3. Додаткова інформація ---
    st.subheader("Найпопулярніші Ключові Слова")
    top_keywords = df.dropna(subset=['keyword_trigger'])['keyword_trigger'].value_counts().nlargest(5)
    if not top_keywords.empty:
        st.table(top_keywords)
    else:
        st.info("Не знайдено даних по ключових словах.")