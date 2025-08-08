# src/dashboard/config_utils.py

import yaml
import streamlit as st

def load_config(config_path):
    """Завантажує конфігурацію з YAML файлу."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error(f"Файл конфігурації не знайдено за шляхом: {config_path}")
        return None
    except Exception as e:
        st.error(f"Помилка при читанні файлу конфігурації: {e}")
        return None

def save_config(config_path, config_data):
    """Зберігає конфігурацію в YAML файл."""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        st.error(f"Помилка при збереженні файлу конфігурації: {e}")
        return False