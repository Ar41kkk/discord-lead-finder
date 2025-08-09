# src/dashboard/data.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from pathlib import Path
from config.settings import settings


# --- Які колонки очікує дашборд у всіх табах ---
_EXPECTED_COLS = [
    # базові
    "id", "message_timestamp", "created_at",
    "message_content", "message_url", "keyword_trigger",
    # джоїни (імена)
    "server_name", "channel_name", "author_name", "bot_user_name",
    # AI/ручні
    "ai_stage_one_status", "ai_stage_two_status", "ai_stage_two_score",
    "manual_status",
]


def _empty_df() -> pd.DataFrame:
    """Порожній DF із повною схемою, щоб UI ніколи не падав."""
    df = pd.DataFrame(columns=_EXPECTED_COLS)
    # типи за замовчуванням
    df["ai_stage_two_score"] = pd.Series(dtype="float64")
    return df


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Гарантуємо наявність усіх потрібних колонок + нормалізація значень."""
    for c in _EXPECTED_COLS:
        if c not in df.columns:
            # розумні дефолти
            if c == "ai_stage_two_score":
                df[c] = 0.0
            else:
                df[c] = ""

    # час: message_timestamp (UTC) — якщо нема, беремо created_at
    if "message_timestamp" in df.columns and df["message_timestamp"].notna().any():
        df["message_timestamp"] = pd.to_datetime(df["message_timestamp"], utc=True, errors="coerce")
    elif "created_at" in df.columns:
        df["message_timestamp"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")

    # статуси/скори
    df["manual_status"]       = df.get("manual_status", pd.Series(dtype=str)).fillna("N/A").astype(str).str.lower()
    df["ai_stage_one_status"] = df.get("ai_stage_one_status", pd.Series(dtype=str)).fillna("N/A").astype(str)
    df["ai_stage_two_status"] = df.get("ai_stage_two_status", pd.Series(dtype=str)).fillna("N/A").astype(str)
    df["ai_stage_two_score"]  = pd.to_numeric(df.get("ai_stage_two_score", 0.0), errors="coerce").fillna(0.0)

    # текстові поля
    for c in ["server_name", "channel_name", "author_name", "bot_user_name",
              "message_content", "message_url", "keyword_trigger"]:
        df[c] = df[c].fillna("").astype(str)

    return df


@st.cache_data(show_spinner=False)
def load_data(db_url: str, db_signature: tuple) -> pd.DataFrame:
    """
    Повертає DataFrame з opportunities + назви ботів/серверів/каналів/авторів.
    Джерело: settings.database.db_url (sqlite).
    Ніколи не кидає KeyError: повертає DF з повною очікуваною схемою.
    """
    # --- 1) Перевіряємо URL і файл БД ---
    db_url_raw = getattr(getattr(settings, "database", object()), "db_url", None)
    if not db_url_raw:
        st.error("❌ Не задано settings.database.db_url.")
        return _empty_df()

    try:
        url = make_url(db_url_raw)
    except Exception as e:
        st.error(f"❌ Некоректний database.db_url: {e}")
        return _empty_df()

    url = make_url(db_url)
    if url.drivername != "sqlite":
        raise RuntimeError("Поки що підтримується лише sqlite")

    db_path = url.database
    if not db_path:
        st.error("❌ У sqlite URL відсутній шлях до файлу БД.")
        return _empty_df()

    db_file = Path(db_path if Path(db_path).is_absolute()
                   else (Path(__file__).resolve().parents[2] / db_path)).resolve()

    if not db_file.exists():
        st.error(f"❌ Файл БД не знайдено: {db_file}")
        return _empty_df()

    st.caption(f"🔌 DB: `{db_file}`")

    # --- 2) Чи є потрібна таблиця? ---
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunities' LIMIT 1")
            ).fetchone()
            if not exists:
                st.info("ℹ️ У БД немає таблиці 'opportunities'.")
                return _empty_df()
    except Exception as e:
        st.warning(f"Не вдалося перевірити структуру БД: {e}")
        return _empty_df()

    # --- 3) Основний запит ---
    query = """
        SELECT
            opp.*,
            acc.name  AS bot_user_name,
            srv.name  AS server_name,
            chn.name  AS channel_name,
            auth.name AS author_name
        FROM opportunities AS opp
        LEFT JOIN discordaccount AS acc ON opp.discovered_by_id = acc.id
        LEFT JOIN server         AS srv ON opp.server_id = srv.id
        LEFT JOIN channel        AS chn ON opp.channel_id = chn.id
        LEFT JOIN author         AS auth ON opp.author_id = auth.id
    """

    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn)
    except Exception as e:
        st.warning(f"Не вдалося виконати SELECT: {e}")
        return _empty_df()

    # --- 4) Порожня таблиця? Повертаємо коректну схему ---
    if df.empty:
        st.info("ℹ️ У 'opportunities' поки немає записів.")
        return _ensure_columns(_empty_df())

    # --- 5) Нормалізація і гарантування колонок ---
    df = _ensure_columns(df)

    st.caption(f"📦 Завантажено рядків: {len(df)}")
    return df
