# src/dashboard/pages/tab_cost_analysis.py

import streamlit as st
from ..constants import AI_QUALIFIED_STATUSES, COST_PER_AI_REQUEST_USD


def display_tab(df):
    """Відображає вкладку аналізу витрат."""
    st.header("💰 Аналіз Витрат та Ефективності")

    if df.empty:
        st.info("Немає даних для аналізу витрат за обраний період.")
        return

    # --- Розрахунок метрик ---
    total_requests = len(df)

    # --- ВИПРАВЛЕННЯ ТУТ ---
    # Використовуємо нову колонку 'ai_stage_two_status'
    ai_qualified_df = df[df['ai_stage_two_status'].isin(AI_QUALIFIED_STATUSES)]
    total_qualified_leads = len(ai_qualified_df)

    # Загальні витрати
    total_cost = total_requests * COST_PER_AI_REQUEST_USD

    # Вартість одного кваліфікованого ліда
    cost_per_lead = total_cost / total_qualified_leads if total_qualified_leads > 0 else 0

    # --- Відображення ---
    st.subheader("Загальні показники")
    col1, col2, col3 = st.columns(3)
    col1.metric("Кількість запитів до AI", value=total_requests)
    col2.metric("Загальні витрати (USD)", value=f"${total_cost:.2f}")
    col3.metric("Вартість 1 кваліфікованого ліда (CPL)", value=f"${cost_per_lead:.3f}")

    st.markdown("---")

    # Аналіз витрат по джерелах
    st.subheader("Витрати в розрізі джерел (Топ-10)")

    cost_by_server = df.groupby('server_name').size().reset_index(name='requests')
    cost_by_server['cost'] = cost_by_server['requests'] * COST_PER_AI_REQUEST_USD
    cost_by_server = cost_by_server.sort_values(by='cost', ascending=False).nlargest(10, 'cost')

    st.dataframe(
        cost_by_server,
        column_config={
            "server_name": "Сервер",
            "requests": "К-сть запитів",
            "cost": st.column_config.NumberColumn(
                "Витрати, $",
                format="$%.2f"
            )
        },
        use_container_width=True, hide_index=True
    )