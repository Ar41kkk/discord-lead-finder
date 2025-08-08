# src/dashboard/pages/tab_lead_funnel.py

import streamlit as st
import plotly.graph_objects as go
from ..constants import AI_QUALIFIED_STATUSES, MANUAL_APPROVED_STATUS # <-- Новий імпорт

def display_tab(df):
    """Відображає вкладку аналізу воронки лідів."""
    st.header("🎯 Аналіз Воронки Лідів")

    # Використовуємо константи
    total_opportunities = len(df)
    ai_qualified_df = df[df['ai_status'].isin(AI_QUALIFIED_STATUSES)]
    manual_approved_df = ai_qualified_df[ai_qualified_df['manual_status'] == MANUAL_APPROVED_STATUS]

    fig_funnel = go.Figure(go.Funnel(
        y=["Потенційні Можливості", "Кваліфіковано AI", "Підтверджено Вручну"],
        x=[total_opportunities, len(ai_qualified_df), len(manual_approved_df)],
        textposition="inside", textinfo="value+percent initial",
        marker={"color": ["#004c99", "#0080ff", "#80c1ff"]}
    ))
    fig_funnel.update_layout(title_text="Воронка Конверсії Можливостей")

    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.plotly_chart(fig_funnel, use_container_width=True)
    with right_col:
        st.subheader("Ключові Показники (KPIs)")
        conv_ai = (len(ai_qualified_df) / total_opportunities) * 100 if total_opportunities > 0 else 0
        conv_manual = (len(manual_approved_df) / len(ai_qualified_df)) * 100 if len(ai_qualified_df) > 0 else 0

        st.metric(label="К-сть можливостей у періоді", value=total_opportunities)
        st.metric(label="Конверсія в кваліфіковані (AI)", value=f"{conv_ai:.1f}%")
        st.metric(label="Конверсія в підтверджені (Manual)", value=f"{conv_manual:.1f}%",
                  help="Відсоток від кваліфікованих AI, які були підтверджені вручну.")