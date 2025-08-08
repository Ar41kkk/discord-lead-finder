# src/dashboard/pages/page_analytics.py

import streamlit as st
from . import (
    tab_overview,
    tab_lead_funnel,
    tab_ai_performance,
    tab_keyword_analysis,
    tab_community_analysis,
    tab_time_analysis,
    tab_cost_analysis,
    tab_detailed_view
)


def display_page(df):
    """Відображає сторінку з усіма аналітичними вкладками."""
    st.header("📈 Аналітичний Центр", divider='rainbow')

    # Створюємо вкладки всередині аналітичної сторінки
    tab_titles = [
        "📊 Огляд", "🎯 Аналіз Воронки", "🧠 Продуктивність AI", "🔑 Ефективність Ключів",
        "👨‍👩‍👧‍👦 Аналіз Спільноти", "⏳ Часовий Аналіз", "💰 Аналіз Витрат", "📄 Детальний Перегляд"
    ]

    tabs = st.tabs(tab_titles)

    with tabs[0]:
        tab_overview.display_tab(df)
    with tabs[1]:
        tab_lead_funnel.display_tab(df)
    with tabs[2]:
        tab_ai_performance.display_tab(df)
    with tabs[3]:
        tab_keyword_analysis.display_tab(df)
    with tabs[4]:
        tab_community_analysis.display_tab(df)
    with tabs[5]:
        tab_time_analysis.display_tab(df)
    with tabs[6]:
        tab_cost_analysis.display_tab(df)
    with tabs[7]:
        tab_detailed_view.display_tab(df)