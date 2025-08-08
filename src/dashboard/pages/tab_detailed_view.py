# src/dashboard/pages/tab_detailed_view.py

import streamlit as st

def display_tab(df):
    """Відображає вкладку з детальною таблицею можливостей."""
    st.header("📄 Детальний перегляд можливостей")

    # Створюємо локальні фільтри, які діють лише в межах цієї вкладки
    st.info("Ви можете додатково відфільтрувати дані, що відображаються в таблиці нижче.")

    col1, col2 = st.columns(2)
    with col1:
        server_list = ["Всі"] + df['server_name'].unique().tolist()
        selected_server = st.selectbox("Фільтр по серверу:", server_list, key="detailed_view_server")

    with col2:
        status_list = ["Всі"] + df['ai_status'].unique().tolist()
        selected_status = st.selectbox("Фільтр по статусу AI:", status_list, key="detailed_view_status")

    # Застосовуємо локальні фільтри
    table_df = df.copy()
    if selected_server != "Всі":
        table_df = table_df[table_df['server_name'] == selected_server]
    if selected_status != "Всі":
        table_df = table_df[table_df['ai_status'] == selected_status]

    st.dataframe(
        table_df[[
            'message_timestamp', 'server_name', 'channel_name', 'author_name',
            'ai_status', 'ai_score', 'manual_status', 'message_content', 'message_url'
        ]],
        use_container_width=True, height=600, hide_index=True
    )