# src/dashboard/pages/tab_overview.py

import streamlit as st
from ..constants import AI_QUALIFIED_STATUSES

def display_tab(df):
    """Відображає головну вкладку з ключовими показниками."""
    st.header("📊 Головні Показники (Overview)")

    # Розраховуємо ключові метрики
    total_opportunities = len(df)
    ai_qualified_df = df[df['ai_status'].isin(AI_QUALIFIED_STATUSES)]
    manual_approved_count = len(df[df['manual_status'] == 'approved'])

    # Конверсія
    ai_conversion_rate = (len(ai_qualified_df) / total_opportunities) * 100 if total_opportunities > 0 else 0

    # Топ-3 ключових слова
    top_keywords = df.dropna(subset=['keyword_trigger'])['keyword_trigger'].value_counts().nlargest(3)

    # Розміщуємо метрики в колонках
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="Всього Можливостей", value=f"{total_opportunities}")

    with col2:
        st.metric(label="Кваліфіковано AI", value=f"{len(ai_qualified_df)}")
        st.metric(label="Конверсія AI", value=f"{ai_conversion_rate:.1f}%")

    with col3:
        st.metric(label="Підтверджено Вручну", value=f"{manual_approved_count}")

    st.markdown("---")

    # Виводимо додаткову корисну інформацію
    st.subheader("Найпопулярніші Ключові Слова")
    if not top_keywords.empty:
        st.table(top_keywords)
    else:
        st.info("Не знайдено даних по ключових словах.")