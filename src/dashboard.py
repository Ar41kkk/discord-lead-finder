# src/dashboard.py

import streamlit as st
import pandas as pd
from pathlib import Path

# Імпортуємо наші власні модулі
from dashboard.data import load_data
from dashboard.pages import (
    page_triage,
    page_analytics,
    page_config,
    page_bot_control
)

def main():
    """Основна функція, що збирає та відображає дашборд."""
    st.set_page_config(page_title="Lead Management Platform", page_icon="🚀", layout="wide")

    # --- ЗАВАНТАЖЕННЯ ДАНИХ ТА КОНФІГУРАЦІЇ ---
    try:
        project_root = Path(__file__).resolve().parent.parent
        db_path = project_root / "db.sqlite3"
        config_path = project_root / "config.yaml"
        df_full = load_data(db_path)
    except Exception as e:
        st.error(f"Помилка при ініціалізації додатку: {e}")
        st.stop()

    if df_full.empty:
        st.warning("Таблиця 'opportunities' порожня. Деякі функції аналітики можуть бути недоступні.")

    # --- БІЧНА ПАНЕЛЬ: НАВІГАЦІЯ ТА ФІЛЬТРИ ---
    with st.sidebar:
        st.title("Lead Gen Platform")

        # --- Навігаційне меню ---
        page = st.radio(
            "Навігація",
            ["📬 Сортування", "📈 Аналітика", "⚙️ Конфігурація", "🤖 Керування Ботом"],
            label_visibility="collapsed"
        )
        st.divider()

        # --- Глобальні фільтри ---
        st.header("Глобальні Фільтри")
        min_date = df_full['message_timestamp'].min().date() if not df_full.empty else pd.Timestamp.now().date()
        max_date = df_full['message_timestamp'].max().date() if not df_full.empty else pd.Timestamp.now().date()
        selected_date_range = st.date_input(
            "Діапазон дат", [min_date, max_date], min_value=min_date, max_value=max_date
        )

    # --- ФІЛЬТРАЦІЯ ДАНИХ ---
    if len(selected_date_range) == 2 and not df_full.empty:
        start_date = pd.to_datetime(selected_date_range[0]).tz_localize('UTC')
        end_date = pd.to_datetime(selected_date_range[1]).tz_localize('UTC').replace(hour=23, minute=59, second=59)
        filtered_df = df_full[
            (df_full['message_timestamp'] >= start_date) & (df_full['message_timestamp'] <= end_date)
            ].copy()
    else:
        filtered_df = df_full.copy()

    # --- ВІДОБРАЖЕННЯ ОБРАНОЇ СТОРІНКИ ---
    if page == "📬 Сортування":
        page_triage.display_page(filtered_df, db_path)
    elif page == "📈 Аналітика":
        page_analytics.display_page(filtered_df)
    elif page == "⚙️ Конфігурація":
        page_config.display_page(config_path)
    elif page == "🤖 Керування Ботом":
        page_bot_control.display_page()


if __name__ == "__main__":
    main()