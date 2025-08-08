# src/dashboard/pages/tab_time_analysis.py

import streamlit as st
import pandas as pd
import plotly.express as px


def display_tab(df):
    """Відображає вкладку часового аналізу."""
    st.header("⏳ Часовий Аналіз Активності")

    # --- ОНОВЛЕНА ЛОГІКА ---
    # Для цього аналізу нас цікавлять лише кваліфіковані ліди другого етапу
    qualified_df = df[df['ai_stage_two_status'].isin(['RELEVANT', 'POSSIBLY_RELEVANT'])].copy()

    if qualified_df.empty:
        st.info("Не знайдено кваліфікованих лідів за обраний період для часового аналізу.")
        return

    st.subheader("Динаміка надходження кваліфікованих лідів")
    leads_over_time = qualified_df.set_index('message_timestamp').resample('D').size().reset_index(name='count')
    fig_time = px.line(
        leads_over_time,
        x='message_timestamp',
        y='count',
        title="Кількість кваліфікованих лідів за днями",
        labels={'message_timestamp': 'Дата', 'count': 'Кількість лідів'}
    )
    st.plotly_chart(fig_time, use_container_width=True)

    st.markdown("---")
    st.subheader("Теплова карта активності: 'Гарячі години'")

    qualified_df['day_of_week'] = qualified_df['message_timestamp'].dt.day_name()
    qualified_df['hour_of_day'] = qualified_df['message_timestamp'].dt.hour
    heatmap_data = qualified_df.pivot_table(
        index='day_of_week',
        columns='hour_of_day',
        values='id',
        aggfunc='count'
    ).fillna(0)
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heatmap_data = heatmap_data.reindex(days_order)
    fig_heatmap = px.imshow(
        heatmap_data,
        labels=dict(x="Година дня", y="День тижня", color="К-сть лідів"),
        x=heatmap_data.columns,
        y=heatmap_data.index,
        title="Кількість лідів за днем тижня та годиною"
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)