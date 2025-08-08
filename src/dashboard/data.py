# src/dashboard/data.py

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from config.settings import settings

@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Повертає DataFrame з усіма колонками opportunities + назви ботів, серверів, каналів, авторів.
    Джерело: settings.database.db_url.
    """
    # розпарсимо URL і перевіримо, що це sqlite
    url = make_url(settings.database.db_url)
    if url.drivername != "sqlite":
        raise RuntimeError("Поки що підтримується лише sqlite")

    try:
        engine = create_engine(settings.database.db_url)
        query = """
        SELECT
            opp.*,
            acc.name AS bot_user_name,
            srv.name AS server_name,
            chn.name AS channel_name,
            auth.name AS author_name
        FROM opportunities AS opp
        LEFT JOIN discordaccount AS acc ON opp.discovered_by_id = acc.id
        LEFT JOIN server AS srv ON opp.server_id = srv.id
        LEFT JOIN channel AS chn ON opp.channel_id = chn.id
        LEFT JOIN author AS auth ON opp.author_id = auth.id
        """
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn)

        if df.empty:
            return df  # повернемо порожній DF із правильною іменованою схемою

        # перетворення time-стовпчика
        df['message_timestamp'] = pd.to_datetime(
            df['message_timestamp'], utc=True, errors='coerce'
        )

        # підготовка статусних колонок
        df['manual_status']       = df['manual_status'].fillna('N/A').str.lower()
        df['ai_stage_two_status'] = df['ai_stage_two_status'].fillna('N/A')
        df['ai_stage_two_score']  = df['ai_stage_two_score'].fillna(0.0)

        return df

    except Exception as e:
        st.warning(f"Не вдалося завантажити data.opportunities: {e}")
        return pd.DataFrame()
