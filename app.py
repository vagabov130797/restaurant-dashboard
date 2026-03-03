import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Система управления рестораном", layout="wide")

DATA_FILE = "data.csv"

USERS = {
    "owner": {"password": "1234", "role": "owner"},
    "admin": {"password": "1111", "role": "admin"}
}

def format_number(n):
    return f"{int(n):,}".replace(",", " ")

def format_currency(n):
    return f"{format_number(n)} ₽"

# =========================
# АВТОРИЗАЦИЯ
# =========================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("🔐 Вход в систему")
    login = st.text_input("Логин")
    password = st.text_input("Пароль", type="password")

    if st.button("Войти"):
        if login in USERS and USERS[login]["password"] == password:
            st.session_state.authenticated = True
            st.session_state.role = USERS[login]["role"]
            st.rerun()
        else:
            st.error("Неверный логин или пароль")
    st.stop()

# =========================
# ЗАГРУЗКА ДАННЫХ
# =========================
if os.path.exists(DATA_FILE):
    data = pd.read_csv(DATA_FILE)
else:
    data = pd.DataFrame(columns=[
        "Дата", "Выручка", "Заказы",
        "Жалобы", "Станция", "Причина"
    ])

if not data.empty:
    data["Станция"] = data["Станция"].astype(str)
    data["Причина"] = data["Причина"].astype(str)

st.title("📊 Система управления рестораном")

# =========================
# АДМИН
# =========================
if st.session_state.role == "admin":

    st.subheader("📝 Ввод данных")

    with st.form("form"):
        date = st.date_input(
            "Дата",
            max_value=pd.Timestamp.today()  # ❌ запрещаем будущие даты
        )
        revenue = st.number_input("Выручка (₽)", min_value=0)
        orders = st.number_input("Количество заказов", min_value=0)
        complaints = st.number_input("Количество жалоб", min_value=0)
        station = st.text_input("Станция")
        reason = st.text_input("Причина жалобы")

        submit = st.form_submit_button("Сохранить")

    if submit:

        new_row = {
            "Дата": str(date),
            "Выручка": revenue,
            "Заказы": orders,
            "Жалобы": complaints,
            "Станция": station if station else "Не указана",
            "Причина": reason if reason else "Не указана"
        }

        if not data.empty and str(date) in data["Дата"].values:
            index = data[data["Дата"] == str(date)].index[0]
            for key in new_row:
                data.at[index, key] = new_row[key]
        else:
            data = pd.concat([data, pd.DataFrame([new_row])], ignore_index=True)

        data.to_csv(DATA_FILE, index=False)
        st.success("Данные сохранены")

    if not data.empty:
        st.subheader("Последние записи")
        st.dataframe(data.tail(5), use_container_width=True, hide_index=True)

# =========================
# ВЛАДЕЛЕЦ
# =========================
if st.session_state.role == "owner":

    if not data.empty:

        data["Дата"] = pd.to_datetime(data["Дата"])
        data = data.sort_values("Дата").reset_index(drop=True)

        st.subheader("📅 Выбор периода")

        start_date = st.date_input("С", data["Дата"].min())
        end_date = st.date_input("По", data["Дата"].max())

        filtered_data = data[
            (data["Дата"] >= pd.to_datetime(start_date)) &
            (data["Дата"] <= pd.to_datetime(end_date))
        ].sort_values("Дата").reset_index(drop=True)

        if filtered_data.empty:
            st.info("Нет данных за выбранный период")
            st.stop()

        # ===== ОСНОВНЫЕ МЕТРИКИ =====
        total_revenue = filtered_data["Выручка"].sum()
        total_orders = filtered_data["Заказы"].sum()
        total_complaints = filtered_data["Жалобы"].sum()
        avg_check = total_revenue / total_orders if total_orders > 0 else 0
        complaint_percent = (total_complaints / total_orders * 100) if total_orders > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Выручка", format_currency(total_revenue))
        col2.metric("Заказы", format_number(total_orders))
        col3.metric("Жалобы", format_number(total_complaints))
        col4.metric("Средний чек", format_currency(avg_check))
        col5.metric("Жалобы %", f"{round(complaint_percent,2)} %")

        # ===== ГРАФИК =====
        st.subheader("📈 Динамика выручки")
        chart_data = filtered_data.set_index("Дата")
        st.line_chart(chart_data["Выручка"])

        # ===== КОНТРОЛЬ ЖАЛОБ =====
        st.subheader("🚨 Контроль жалоб по дням")

        def complaint_status(x):
            if x > 3:
                return "🔴 Критично"
            elif x >= 2:
                return "🟡 Внимание"
            else:
                return "🟢 Норма"

        complaints_table = filtered_data.copy()
        complaints_table["Дата"] = complaints_table["Дата"].dt.strftime("%d.%m.%Y")
        complaints_table["Статус"] = complaints_table["Жалобы"].apply(complaint_status)

        st.dataframe(
            complaints_table[["Дата", "Жалобы", "Станция", "Причина", "Статус"]],
            use_container_width=True,
            hide_index=True
        )

        # ===== АНАЛИЗ РОСТА / ПАДЕНИЯ =====
        st.subheader("📉📈 Анализ роста / падения")

        analysis = filtered_data.copy()
        analysis["Предыдущий день"] = analysis["Выручка"].shift(1)
        analysis["Изменение (%)"] = (
            (analysis["Выручка"] - analysis["Предыдущий день"])
            / analysis["Предыдущий день"]
            * 100
        )

        drops = analysis[analysis["Изменение (%)"] <= -15]
        growth = analysis[analysis["Изменение (%)"] >= 15]

        if not drops.empty:
            st.error("🔴 Падение более 15%")
            drops["Дата"] = drops["Дата"].dt.strftime("%d.%m.%Y")
            st.dataframe(drops[["Дата", "Выручка", "Изменение (%)"]], hide_index=True)

        if not growth.empty:
            st.success("🟢 Рост более 15%")
            growth["Дата"] = growth["Дата"].dt.strftime("%d.%m.%Y")
            st.dataframe(growth[["Дата", "Выручка", "Изменение (%)"]], hide_index=True)

        # ===== ЛУЧШИЙ / ХУДШИЙ ДЕНЬ =====
        st.subheader("🏆 Лучший и худший день")

        best_day = filtered_data.loc[filtered_data["Выручка"].idxmax()]
        worst_day = filtered_data.loc[filtered_data["Выручка"].idxmin()]

        col1, col2 = st.columns(2)
        col1.success(f"Лучший: {best_day['Дата'].strftime('%d.%m.%Y')} — {format_currency(best_day['Выручка'])}")
        col2.error(f"Худший: {worst_day['Дата'].strftime('%d.%m.%Y')} — {format_currency(worst_day['Выручка'])}")

        # ===== ДНИ НЕДЕЛИ =====
        st.subheader("📅 Анализ по дням недели")
        weekday_data = filtered_data.copy()
        weekday_data["День недели"] = weekday_data["Дата"].dt.day_name()
        weekday_analysis = weekday_data.groupby("День недели")["Выручка"].mean()
        st.bar_chart(weekday_analysis)

        # ===== СЕЗОННОСТЬ =====
        st.subheader("📆 Анализ сезонности")
        month_data = filtered_data.copy()
        month_data["Месяц"] = month_data["Дата"].dt.month
        month_analysis = month_data.groupby("Месяц")["Выручка"].mean()

        if len(month_analysis) >= 3:
            st.bar_chart(month_analysis)
        else:
            st.info("Недостаточно данных для анализа сезонности")

    else:
        st.info("Нет данных")