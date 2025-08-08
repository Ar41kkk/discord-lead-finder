# src/dashboard/plotting.py

import plotly.express as px
import streamlit as st

def create_bar_chart(df, x_col, y_col, title, x_label, y_label, top_n=10):
    """
    Створює та відображає горизонтальний стовпчастий графік для топ-N значень.
    """
    # Розраховуємо топ-N значень
    top_data = df[y_col].value_counts().nlargest(top_n).reset_index()
    top_data.columns = [y_col, x_col] # Перейменовуємо колонки для графіка

    fig = px.bar(
        top_data,
        x=x_col,
        y=y_col,
        orientation='h',
        title=title,
        labels={x_col: x_label, y_col: y_label}
    )
    # Сортуємо осі, щоб найбільше значення було вгорі
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig, use_container_width=True)