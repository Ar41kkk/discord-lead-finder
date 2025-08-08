# ── src/dashboard/pages/page_bot_control.py ──────────────────────────────────────
import streamlit as st
from pathlib import Path
from typing import Any

from streamlit_autorefresh import st_autorefresh

from dashboard.bot_utils import get_status, start_bot, stop_bot, log_file
from dashboard.constants import AI_QUALIFIED_STATUSES, MANUAL_APPROVED_STATUS
from config.settings import settings


def display_page(df_full: Any) -> None:
    """Сторінка керування ботами + live-статистика."""
    st.header("🤖 Керування Ботами")
    st_autorefresh(interval=2_000, key="bot_control_refresh")

    # ── кнопки «старт / стоп усіх» ───────────────────────────────────────────────
    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("🚀 Старт усіх", use_container_width=True):
            for acc in settings.discord.accounts:
                start_bot(acc.name)
    with col_stop:
        if st.button("🛑 Стоп усіх", use_container_width=True):
            for acc in settings.discord.accounts:
                stop_bot(acc.name)

    st.divider()

    # ── для кожного акаунта показуємо статус, метрики, логи ─────────────────────
    for acc in settings.discord.accounts:
        raw_name = acc.name                    # «Tyomizxxx»
        nick_prefix = raw_name.lower()         # «tyomizxxx»

        # ① статус процесу --------------------------------------------------------
        # ① статус процесу --------------------------------------------------------
        state = get_status(raw_name)
        emoji = {"Running": "✅", "Launching": "⏳",
                 "Stopped": "❌"}.get(state, "⚠️")
        st.subheader(f"{raw_name} — {state} {emoji}")

        # ② DataFrame slice лише для цього бота ----------------------------------
        if df_full is not None and not df_full.empty:
            prefix = raw_name.lower()
            mask = (
                df_full["bot_user_name"]
                .fillna("")  # щоб не було NaN
                .str.lower()
                .str.split("#", n=1)  # ['parfolemu16', '1234'] або ['parfolemu16']
                .str[0]  # префікс
                .eq(prefix)  # точний збіг
            )
            sub = df_full[mask]
        else:
            sub = None

        # ③ метрики --------------------------------------------------------------
        if sub is not None and not sub.empty:
            total_triggers    = sub["keyword_trigger"].notna().sum()
            stage1_passed     = sub["ai_stage_one_status"].isin(
                                    AI_QUALIFIED_STATUSES).sum()
            stage2_passed     = sub["ai_stage_two_status"].isin(
                                    AI_QUALIFIED_STATUSES).sum()
            manually_approved = (sub["manual_status"]
                                   .str.lower()
                                   .eq(MANUAL_APPROVED_STATUS)).sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Тригери",        total_triggers)
            c2.metric("Етап 1 pass",    stage1_passed)
            c3.metric("Етап 2 pass",    stage2_passed)
            c4.metric("Підтв. вручну",  manually_approved)
        else:
            st.info("Дані для цього акаунта відсутні або БД порожня.")

        # ④ LIVE-логи ------------------------------------------------------------
        lf = log_file(raw_name)
        if lf.exists():
            with st.expander(f"📄 Логи {raw_name}", expanded=False):
                tail = lf.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
                st.code("\n".join(tail), language="bash")
        else:
            st.info("Лог-файл ще не створено.")

        st.divider()
