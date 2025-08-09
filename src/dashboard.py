# src/dashboard.py
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from sqlalchemy.engine import make_url

from config.settings import settings
from dashboard.data import load_data
from dashboard.pages import (
    page_triage,
    page_analytics,
    page_config,
    page_bot_control,
)

# ---- helpers -------------------------------------------------------------
def _resolve_db_file(db_url: str) -> Path:
    """Перетворює sqlite URL -> абсолютний шлях до файлу БД."""
    url = make_url(db_url)
    p = Path(url.database) if url.database else None
    if not p:
        return Path()  # порожній шлях -> сигнатура буде нульова
    if not p.is_absolute():
        # <repo_root>/...  (src/dashboard.py -> <repo_root>)
        repo_root = Path(__file__).resolve().parents[1].parents[0]
        p = (repo_root / p).resolve()
    return p

def _db_signature(db_url: str) -> tuple:
    """
    Сигнатура БД для кешу: (mtime,size) основного файлу + -wal/-shm, якщо є.
    Змінились файли -> змінилась сигнатура -> перераховується cache_data.
    """
    p = _resolve_db_file(db_url)
    files = [p, p.with_suffix(p.suffix + "-wal"), p.with_suffix(p.suffix + "-shm")]
    sig = []
    for f in files:
        if f and f.exists():
            s = f.stat()
            sig.append((int(s.st_mtime_ns), int(s.st_size)))
        else:
            sig.append((0, 0))
    return tuple(sig)
# -------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Lead Management Platform", page_icon="🚀", layout="wide")

    # глобальний авто-рефреш (підбери інтервал як зручно)
    st_autorefresh(interval=5_000, key="global_refresh")

    # --- 1) Завантажуємо всю таблицю opportunities з БД ---
    try:
        db_sig = _db_signature(settings.database.db_url)
        # ВАЖЛИВО: load_data тепер приймає (db_url, db_signature)
        df_full = load_data(settings.database.db_url, db_sig)
    except Exception as e:
        st.error(f"Помилка при ініціалізації додатку: {e}")
        st.stop()

    # --- 2) Бічна панель: навігація + фільтри ---
    with st.sidebar:
        st.title("Lead Gen Platform")
        page = st.radio(
            "Навігація",
            ["📬 Сортування", "📈 Аналітика", "⚙️ Конфігурація", "🤖 Керування Ботом"],
            label_visibility="collapsed",
        )
        st.divider()

        # Фільтр за акаунтом
        if not df_full.empty and "bot_user_name" in df_full.columns:
            bots = df_full["bot_user_name"].dropna().unique().tolist()
            accounts_list = ["Всі акаунти"] + sorted(bots)
        else:
            accounts_list = ["Всі акаунти"]
        selected_account = st.selectbox("Акаунт бота", accounts_list)

        # Фільтр за датою
        if not df_full.empty and "message_timestamp" in df_full.columns and df_full["message_timestamp"].notna().any():
            min_date = pd.to_datetime(df_full["message_timestamp"]).min().date()
            max_date = pd.to_datetime(df_full["message_timestamp"]).max().date()
        else:
            today = pd.Timestamp.utcnow().date()
            min_date = max_date = today

        selected_date_range = st.date_input(
            "Діапазон дат",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date,
        )

    # --- 3) Фільтруємо DataFrame відповідно до вибору ---
    df = df_full.copy()
    if not df.empty and "message_timestamp" in df.columns:
        # по датах
        start = pd.to_datetime(selected_date_range[0]).tz_localize("UTC")
        end = pd.to_datetime(selected_date_range[1]).tz_localize("UTC").replace(hour=23, minute=59, second=59)
        df = df[(df["message_timestamp"] >= start) & (df["message_timestamp"] <= end)]

        # по акаунту
        if selected_account != "Всі акаунти" and "bot_user_name" in df.columns:
            df = df[df["bot_user_name"] == selected_account]

    # --- 4) Рендер сторінки за вибором ---
    if page == "📬 Сортування":
        page_triage.display_page(df)
    elif page == "📈 Аналітика":
        page_analytics.display_page(df)
    elif page == "⚙️ Конфігурація":
        config_path = Path(__file__).resolve().parents[1] / "config.yaml"
        page_config.display_page(config_path)
    else:  # "🤖 Керування Ботом"
        page_bot_control.display_page(df_full)


if __name__ == "__main__":
    main()
