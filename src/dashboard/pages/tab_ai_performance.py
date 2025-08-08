# src/dashboard/pages/tab_ai_performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ..constants import AI_QUALIFIED_STATUSES, MANUAL_APPROVED_STATUS


def display_tab(df):
    """Відображає вкладку аналізу продуктивності AI."""
    st.header("🧠 Аналіз Продуктивності AI-агента")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Розподіл статусів від AI (Етап 2)")
        # Використовуємо ai_stage_two_status для фінальних вердиктів
        status_counts = df[df['ai_stage_two_status'] != 'N/A']['ai_stage_two_status'].value_counts()
        if not status_counts.empty:
            fig_status_pie = px.pie(values=status_counts.values, names=status_counts.index,
                                    color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_status_pie, use_container_width=True)
        else:
            st.info("Немає даних другого етапу для побудови діаграми.")

    with col2:
        st.subheader("Розподіл впевненості AI (Score, Етап 2)")
        # Використовуємо ai_stage_two_score
        score_df = df[df['ai_stage_two_score'] > 0]
        if not score_df.empty:
            fig_score_hist = px.histogram(score_df, x="ai_stage_two_score", nbins=20,
                                          title="Частота score від 0.0 до 1.0")
            st.plotly_chart(fig_score_hist, use_container_width=True)
        else:
            st.info("Немає даних другого етапу для побудови гістограми.")

    st.markdown("---")
    st.subheader("Матриця невідповідностей та Метрики Якості")

    # Аналізуємо тільки ті, де є ручна оцінка
    analysis_df = df[df['manual_status'].isin([MANUAL_APPROVED_STATUS, 'rejected'])].copy()

    if analysis_df.empty:
        st.warning(
            "Недостатньо даних з ручною оцінкою ('approved'/'rejected') для побудови матриці та розрахунку метрик.")
        return

    # --- ОНОВЛЕНА ЛОГІКА ---
    # Рішення AI базується на результаті другого етапу
    analysis_df['ai_decision'] = analysis_df['ai_stage_two_status'].apply(
        lambda x: 'Кваліфіковано' if x in AI_QUALIFIED_STATUSES else 'Відхилено')
    analysis_df['manual_decision'] = analysis_df['manual_status'].apply(
        lambda x: 'Підтверджено' if x == MANUAL_APPROVED_STATUS else 'Відхилено')

    confusion_matrix = pd.crosstab(analysis_df['manual_decision'], analysis_df['ai_decision'],
                                   rownames=['Рішення людини'], colnames=['Рішення AI'])

    # Розрахунок метрик
    tp = confusion_matrix.loc['Підтверджено', 'Кваліфіковано'] if (
                'Підтверджено' in confusion_matrix.index and 'Кваліфіковано' in confusion_matrix.columns) else 0
    fp = confusion_matrix.loc['Відхилено', 'Кваліфіковано'] if (
                'Відхилено' in confusion_matrix.index and 'Кваліфіковано' in confusion_matrix.columns) else 0
    fn = confusion_matrix.loc['Підтверджено', 'Відхилено'] if (
                'Підтверджено' in confusion_matrix.index and 'Відхилено' in confusion_matrix.columns) else 0

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    # Відображення
    col_matrix, col_metrics = st.columns(2)
    with col_matrix:
        fig_conf_matrix = go.Figure(data=go.Heatmap(
            z=confusion_matrix.values, x=confusion_matrix.columns, y=confusion_matrix.index,
            hoverongaps=False, colorscale='Blues', text=confusion_matrix.values, texttemplate="%{text}"
        ))
        fig_conf_matrix.update_layout(title="Порівняння рішень")
        st.plotly_chart(fig_conf_matrix, use_container_width=True)

    with col_metrics:
        st.subheader("Оцінка якості AI")
        st.metric(label="Точність (Precision)", value=f"{precision:.2%}",
                  help="Частка правильно визначених лідів серед усіх, що AI назвав лідами. Показує, наскільки можна довіряти позитивним вердиктам AI.")
        st.metric(label="Повнота (Recall)", value=f"{recall:.2%}",
                  help="Частка реальних лідів, яку AI зміг знайти. Показує, скільки лідів ми не пропускаємо.")
        st.metric(label="F1-Score", value=f"{f1_score:.2f}",
                  help="Баланс між Точністю та Повнотою.")