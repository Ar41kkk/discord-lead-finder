import streamlit as st
import time
import yaml
from pathlib import Path
from ..config_utils import load_config, save_config

from dashboard.bot_utils import get_status, start_bot, stop_bot


def display_page(config_path: Path):
    """Відображає вкладку для редагування конфігурації з функцією перезапуску ботів."""
    st.header("⚙️ Редактор Конфігурації", divider='rainbow')

    config_data = load_config(config_path)
    if config_data is None:
        return

    tab_main, tab_ai, tab_discord, tab_advanced = st.tabs([
        "🔑 Ключові слова", "🧠 AI", "💬 Discord", "🛠️ Розширені"
    ])

    with st.form(key="config_form"):
        # --- Ключові слова ---
        with tab_main:
            st.subheader("Слова-тригери")
            keywords_str = "\n".join(config_data.get('keywords', []))
            edited_keywords = st.text_area(
                "Кожне слово/фразу з нового рядка",
                value=keywords_str,
                height=300,
                key="keywords_area"
            )

        # --- AI налаштування ---
        with tab_ai:
            s1 = config_data.get('openai', {}).get('stage_one', {})
            s2 = config_data.get('openai', {}).get('stage_two', {})

            st.subheader("Етап 1 (Stage One)")
            edited_s1_model = st.text_input(
                "Модель AI (Stage One)",
                value=s1.get('model', 'gpt-3.5-turbo'),
                key="s1_model"
            )
            edited_s1_prompt = st.text_area(
                "Промпт AI (Stage One)",
                value=s1.get('system_prompt', ''),
                height=200,
                key="s1_prompt"
            )

            st.divider()
            st.subheader("Етап 2 (Stage Two)")
            edited_s2_model = st.text_input(
                "Модель AI (Stage Two)",
                value=s2.get('model', 'gpt-4o-mini'),
                key="s2_model"
            )
            edited_s2_prompt = st.text_area(
                "Промпт AI (Stage Two)",
                value=s2.get('system_prompt', ''),
                height=200,
                key="s2_prompt"
            )

        # --- Discord налаштування ---
        with tab_discord:
            discord_cfg = config_data.get('discord', {})
            st.subheader("Discord: трекінг каналів")
            edited_track_all = st.toggle(
                "Трекати всі канали?",
                value=discord_cfg.get('track_all_channels', True),
                key="track_all_toggle"
            )
            whitelist_str = "\n".join(map(str, discord_cfg.get('channel_whitelist', [])))
            edited_whitelist = st.text_area(
                "Білий список ID каналів",
                value=whitelist_str,
                height=150,
                key="whitelist_area"
            )

        # --- Інші налаштування ---
        with tab_advanced:
            st.subheader("Інші параметри")
            edited_days = st.number_input(
                "Глибина історії (днів)",
                value=config_data.get('history_days', 7),
                min_value=1,
                key="history_days_input"
            )
            levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            edited_level = st.selectbox(
                "Рівень логів",
                options=levels,
                index=levels.index(config_data.get('log_level', 'INFO')),
                key="log_level_select"
            )

        st.divider()
        submitted = st.form_submit_button("💾 Зберегти та Перезапустити активні боти")


    if not submitted:
        return

    # Збираємо й зберігаємо нові налаштування
    updated = config_data.copy()
    updated['keywords'] = [w.strip() for w in edited_keywords.splitlines() if w.strip()]

    updated.setdefault('openai', {}).setdefault('stage_one', {})['model'] = edited_s1_model
    updated['openai']['stage_one']['system_prompt'] = edited_s1_prompt
    updated.setdefault('openai', {}).setdefault('stage_two', {})['model'] = edited_s2_model
    updated['openai']['stage_two']['system_prompt'] = edited_s2_prompt

    updated.setdefault('discord', {})['track_all_channels'] = edited_track_all
    updated['discord']['channel_whitelist'] = [
        int(x.strip()) for x in edited_whitelist.splitlines() if x.strip()
    ]

    updated['history_days'] = edited_days
    updated['log_level'] = edited_level

    if save_config(config_path, updated):
        st.success("Конфігурацію збережено!")
    else:
        st.error("Не вдалося зберегти конфігурацію.")
        return

    # Перезапускаємо ті боти, що зараз Running
    with st.spinner("Перезапуск ботів..."):
        cnt = 0
        for acc in updated.get('discord', {}).get('accounts', []):
            name = acc.get('name')
            if name and get_status(name) == "Running":
                stop_bot(name)
                time.sleep(1)
                start_bot(name)
                time.sleep(1)
                cnt += 1

    if cnt:
        st.success(f"Перезапущено {cnt} бот(ів).")
    else:
        st.info("Не знайдено запущених ботів для перезапуску.")
