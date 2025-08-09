# src/dashboard/pages/tab_ai_performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ..constants import AI_QUALIFIED_STATUSES, MANUAL_APPROVED_STATUS

def display_tab(df: pd.DataFrame):
    """Відображає вкладку аналізу продуктивності AI з безпечними перевірками колонок."""
    st.header("🧠 Аналіз Продуктивності AI-агента")

    if df is None or df.empty:
        st.info("Немає даних для аналізу.")
        return

    # ---- Безпечні доступи до потрібних колонок
    s2_status = df.get("ai_stage_two_status")
    s2_score  = df.get("ai_stage_two_score")
    manual    = df.get("manual_status")

    # ---- Блок 1: Розподіл статусів (Етап 2)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Розподіл статусів від AI (Етап 2)")
        if s2_status is None:
            st.warning("Відсутня колонка 'ai_stage_two_status' у даних.")
        else:
            s2_clean = s2_status.astype(str).fillna("N/A")
            status_counts = s2_clean[s2_clean.ne("N/A")].value_counts()
            if not status_counts.empty:
                fig_status_pie = px.pie(values=status_counts.values, names=status_counts.index,
                                        title="AI Stage 2 — розподіл вердиктів")
                st.plotly_chart(fig_status_pie, use_container_width=True)
            else:
                st.info("Немає валідних значень для побудови діаграми.")

    # ---- Блок 2: Гістограма score (Етап 2)
    with col2:
        st.subheader("Розподіл впевненості AI (Score, Етап 2)")
        if s2_score is None:
            st.warning("Відсутня колонка 'ai_stage_two_score' у даних.")
        else:
            scores = pd.to_numeric(s2_score, errors="coerce")
            score_df = df.assign(ai_stage_two_score=scores)
            score_df = score_df[score_df["ai_stage_two_score"].notna() & (score_df["ai_stage_two_score"] > 0)]
            if not score_df.empty:
                fig_score_hist = px.histogram(score_df, x="ai_stage_two_score", nbins=20,
                                              title="Частота score від 0.0 до 1.0")
                st.plotly_chart(fig_score_hist, use_container_width=True)
            else:
                st.info("Немає даних score для побудови гістограми.")

    st.markdown("---")
    st.subheader("Матриця відповідностей та Метрики Якості")

    # Для матриці потрібні: ручне рішення та рішення AI (Етап 2)
    if (s2_status is None) or (manual is None):
        st.warning("Потрібні колонки 'ai_stage_two_status' та 'manual_status' для розрахунку метрик.")
        return

    work = df.copy()
    work["manual_status"] = manual.astype(str).str.lower().fillna("n/a")
    work["ai_stage_two_status"] = s2_status.astype(str).fillna("N/A")

    # Тільки де є ручна оцінка (approved / rejected)
    analysis_df = work[work["manual_status"].isin([MANUAL_APPROVED_STATUS, "rejected"])].copy()
    if analysis_df.empty:
        st.info("Недостатньо даних з ручною оцінкою ('approved'/'rejected').")
        return

    analysis_df["ai_decision"] = analysis_df["ai_stage_two_status"].apply(
        lambda x: "Кваліфіковано" if x in AI_QUALIFIED_STATUSES else "Відхилено"
    )
    analysis_df["manual_decision"] = analysis_df["manual_status"].apply(
        lambda x: "Підтверджено" if x == MANUAL_APPROVED_STATUS else "Відхилено"
    )

    cm = pd.crosstab(analysis_df["manual_decision"], analysis_df["ai_decision"],
                     rownames=["Рішення людини"], colnames=["Рішення AI"])

    # Обчислюємо метрики захищено
    tp = cm.loc["Підтверджено", "Кваліфіковано"] if ("Підтверджено" in cm.index and "Кваліфіковано" in cm.columns) else 0
    fp = cm.loc["Відхилено", "Кваліфіковано"]     if ("Відхилено" in cm.index and "Кваліфіковано" in cm.columns) else 0
    fn = cm.loc["Підтверджено", "Відхилено"]      if ("Підтверджено" in cm.index and "Відхилено" in cm.columns) else 0

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1_score  = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    col_matrix, col_metrics = st.columns(2)
    with col_matrix:
        if cm.empty:
            st.info("Недостатньо даних для матриці.")
        else:
            fig_conf_matrix = go.Figure(data=go.Heatmap(
                z=cm.values, x=cm.columns, y=cm.index,
                hoverongaps=False, colorscale='Blues', text=cm.values, texttemplate="%{text}"
            ))
            fig_conf_matrix.update_layout(title="Порівняння рішень (людина vs AI)")
            st.plotly_chart(fig_conf_matrix, use_container_width=True)

    with col_metrics:
        st.subheader("Оцінка якості AI")
        st.metric(label="Точність (Precision)", value=f"{precision:.2%}")
        st.metric(label="Повнота (Recall)",    value=f"{recall:.2%}")
        st.metric(label="F1-Score",            value=f"{f1_score:.2%}")
