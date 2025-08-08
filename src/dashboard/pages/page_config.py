# src/dashboard/pages/page_config.py

import streamlit as st
import time
from ..config_utils import load_config, save_config
from ..bot_utils import get_bot_status, start_bot, stop_bot  # <-- Нові імпорти


def display_page(config_path):
    """Відображає вкладку для редагування конфігурації з функцією перезапуску бота."""
    st.header("⚙️ Редактор Конфігурації", divider='rainbow')

    config_data = load_config(config_path)
    if config_data is None:
        return

    basic_tab, advanced_tab = st.tabs(["Базові налаштування", "Розширені налаштування"])

    with st.form(key="config_form"):
        with basic_tab:
            st.subheader("Основні параметри для щоденного використання")
            st.markdown("#### Ключові слова для пошуку")
            keywords_str = "\n".join(config_data.get('keywords', []))
            edited_keywords = st.text_area("Введіть кожне слово з нового рядка", value=keywords_str, height=200,
                                           help="Слова, на які буде реагувати бот.")
            st.markdown("#### Налаштування AI")
            openai_config = config_data.get('openai', {})
            edited_system_prompt = st.text_area("Системний промпт для AI", value=openai_config.get('system_prompt', ''),
                                                height=300,
                                                help="Основна інструкція, яка визначає поведінку AI-агента.")
            st.markdown("#### Налаштування Discord")
            discord_config = config_data.get('discord', {})
            edited_track_all = st.toggle("Відстежувати всі канали?",
                                         value=discord_config.get('track_all_channels', True),
                                         help="Якщо вимкнено, бот буде працювати лише з каналами з білого списку.")
            whitelist_str = "\n".join(map(str, discord_config.get('channel_whitelist', [])))
            edited_whitelist = st.text_area("Білий список ID каналів (якщо відстеження не всіх)", value=whitelist_str,
                                            height=150, help="Введіть ID кожного каналу з нового рядка.")

        with advanced_tab:
            st.subheader("Детальні налаштування для тонкої конфігурації")
            st.markdown("##### Загальні")
            edited_history_days = st.number_input("Глибина сканування історії (днів)",
                                                  value=config_data.get('history_days', 7), min_value=1)
            edited_log_level = st.selectbox("Рівень логування",
                                            options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                            index=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(
                                                config_data.get('log_level', 'INFO')))
            st.markdown("##### Параметри OpenAI")
            col1, col2, col3 = st.columns(3)
            edited_openai_model = col1.text_input("Модель", value=openai_config.get('model', 'gpt-4o-mini'))
            edited_openai_temp = col2.number_input("Температура", value=openai_config.get('temperature', 0.0),
                                                   min_value=0.0, max_value=2.0, step=0.1)
            edited_openai_retries = col3.number_input("Кількість спроб (retries)",
                                                      value=openai_config.get('max_retries', 3), min_value=0)
            st.markdown("##### Параметри Discord")
            col_d1, col_d2, col_d3 = st.columns(3)
            edited_discord_channels = col_d1.number_input("Одночасних каналів (concurrent)",
                                                          value=discord_config.get('concurrent_channels', 12),
                                                          min_value=1)
            edited_discord_pause = col_d2.number_input("Пауза між запитами (сек)",
                                                       value=discord_config.get('batch_pause_seconds', 0.3),
                                                       min_value=0.0, step=0.1)
            st.markdown("##### Назви аркушів Google Sheets")
            gs_config = config_data.get('google_sheet', {})
            col_gs1, col_gs2 = st.columns(2)
            edited_gs_live = col_gs1.text_input("Live Sheet", value=gs_config.get('live_sheet_name', 'Live'))
            edited_gs_stats = col_gs2.text_input("Stats Sheet", value=gs_config.get('stats_sheet_name', 'Stats'))
            edited_gs_leads = col_gs1.text_input("Leads Sheet", value=gs_config.get('leads_sheet_name', 'Leads'))

        st.markdown("---")
        # Змінюємо текст кнопки для ясності
        submitted = st.form_submit_button("💾 Зберегти та Перезапустити Бота", use_container_width=True, type="primary")

        if submitted:
            # Збираємо всі оновлені дані з обох вкладок
            updated_config = config_data.copy()
            updated_config['keywords'] = [kw.strip() for kw in edited_keywords.split("\n") if kw.strip()]
            updated_config.setdefault('openai', {})['system_prompt'] = edited_system_prompt
            updated_config.setdefault('discord', {})['track_all_channels'] = edited_track_all
            updated_config.setdefault('discord', {})['channel_whitelist'] = [int(ch_id.strip()) for ch_id in
                                                                             edited_whitelist.split("\n") if
                                                                             ch_id.strip()]
            updated_config['history_days'] = edited_history_days
            updated_config['log_level'] = edited_log_level
            updated_config.setdefault('openai', {})['model'] = edited_openai_model
            updated_config.setdefault('openai', {})['temperature'] = edited_openai_temp
            updated_config.setdefault('openai', {})['max_retries'] = edited_openai_retries
            updated_config.setdefault('discord', {})['concurrent_channels'] = edited_discord_channels
            updated_config.setdefault('discord', {})['batch_pause_seconds'] = edited_discord_pause
            updated_config.setdefault('google_sheet', {})['live_sheet_name'] = edited_gs_live
            updated_config.setdefault('google_sheet', {})['stats_sheet_name'] = edited_gs_stats
            updated_config.setdefault('google_sheet', {})['leads_sheet_name'] = edited_gs_leads

            if save_config(config_path, updated_config):
                st.success("Конфігурацію успішно збережено!")

                # --- НОВА ЛОГІКА ПЕРЕЗАПУСКУ ---
                status_info = get_bot_status()

                if status_info["status"] == "Running":
                    with st.spinner("Зупиняю поточний процес бота..."):
                        stop_bot()
                        time.sleep(3)  # Даємо час процесу повністю завершитись

                with st.spinner("Запускаю бота з новою конфігурацією..."):
                    start_bot()
                    time.sleep(3)  # Даємо боту час на ініціалізацію

                st.success("Бот успішно перезапущений з новими налаштуваннями!")
                time.sleep(2)
                st.rerun()
            else:
                st.error("Не вдалося зберегти конфігурацію.")
