# src/dashboard.py

import streamlit as st
import pandas as pd
from pathlib import Path

from dashboard.data import load_data
from dashboard.pages import (
    page_triage,
    page_analytics,
    page_config,
    page_bot_control
)

def main():
    st.set_page_config(
        page_title="Lead Management Platform",
        page_icon="🚀",
        layout="wide",
    )

    # --- 1) Завантажуємо всю таблицю opportunities з БД ---
    try:
        df_full = load_data()
    except Exception as e:
        st.error(f"Помилка при ініціалізації додатку: {e}")
        st.stop()

    # --- 2) Бічна панель: навігація + фільтри ---
    with st.sidebar:
        st.title("Lead Gen Platform")
        page = st.radio(
            "Навігація",
            ["📬 Сортування", "📈 Аналітика", "⚙️ Конфігурація", "🤖 Керування Ботом"],
            label_visibility="collapsed"
        )
        st.divider()

        # Фільтр за акаунтом
        if not df_full.empty and "bot_user_name" in df_full.columns:
            bots = df_full['bot_user_name'].dropna().unique().tolist()
            accounts_list = ["Всі акаунти"] + sorted(bots)
        else:
            accounts_list = ["Всі акаунти"]
        selected_account = st.selectbox("Акаунт бота", accounts_list)

        # Фільтр за датою
        if not df_full.empty:
            min_date = df_full['message_timestamp'].min().date()
            max_date = df_full['message_timestamp'].max().date()
        else:
            today = pd.Timestamp.utcnow().date()
            min_date = max_date = today

        selected_date_range = st.date_input(
            "Діапазон дат",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )

    # --- 3) Фільтруємо DataFrame відповідно до вибору ---
    df = df_full.copy()
    if not df.empty:
        # по датах
        start = pd.to_datetime(selected_date_range[0]).tz_localize("UTC")
        end = pd.to_datetime(selected_date_range[1]).tz_localize("UTC").replace(
            hour=23, minute=59, second=59
        )
        df = df[(df['message_timestamp'] >= start) & (df['message_timestamp'] <= end)]

        # по акаунту
        if selected_account != "Всі акаунти":
            df = df[df['bot_user_name'] == selected_account]

    # --- 4) Рендер сторінки за вибором ---
    if page == "📬 Сортування":
        # Тепер display_page приймає лише DataFrame
        page_triage.display_page(df)

    elif page == "📈 Аналітика":
        page_analytics.display_page(df)

    elif page == "⚙️ Конфігурація":
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        page_config.display_page(config_path)

    else:  # "🤖 Керування Ботом"
        # Для бот-контролю передаємо повний набір даних
        page_bot_control.display_page(df_full)


if __name__ == "__main__":
    main()
