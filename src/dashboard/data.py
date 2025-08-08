# src/dashboard/data.py

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

@st.cache_data
def load_data(db_path):
    """
    Завантажує дані з бази, кешує результат та виконує базову обробку.
    """
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        data = pd.read_sql("SELECT * FROM opportunities", engine)
        data['message_timestamp'] = pd.to_datetime(data['message_timestamp'], utc=True)
        data['manual_status'] = data['manual_status'].fillna('N/A').str.lower()
        return data
    except Exception as e:
        # Ми повертаємо помилку, а головний скрипт її перехопить
        raise ConnectionError(f"Не вдалося завантажити дані з бази даних: {e}")