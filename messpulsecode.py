import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import sqlite3
from datetime import datetime, timedelta, date
import random

# ---------------- DATABASE ----------------

conn = sqlite3.connect("messpulse.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    username TEXT PRIMARY KEY,
    room TEXT,
    password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    meal TEXT,
    rating INTEGER,
    comment TEXT,
    submitted_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS streaks(
    username TEXT PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_active_date TEXT,
    total_visits INTEGER DEFAULT 0,
    total_ratings INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS checkins(
    username TEXT,
    checkin_date TEXT,
    meal TEXT,
    status TEXT,
    PRIMARY KEY (username, checkin_date, meal)
)
""")

conn.commit()

# ---------------- SYNTHETIC DATASET ----------------


@st.cache_data
def load_mess_data():
    random.seed(42)
    np.random.seed(42)
    dates = [datetime(2026, 5, 1) + timedelta(days=i) for i in range(35)]
    meals = ["Breakfast", "Lunch", "Snacks", "Dinner"]
    rows = []
    for d in dates:
        dow = d.weekday()
        for meal in meals:
            base = {"Breakfast": 110, "Lunch": 160,
                    "Snacks": 80, "Dinner": 150}[meal]
            weekend_drop = 0.75 if dow >= 5 else 1.0
            noise = np.random.randint(-20, 20)
            attendance = int(base * weekend_drop + noise)
            attendance = max(30, min(200, attendance))
            planned = 200
            waste_kg = round((planned - attendance) * 0.35 +
                             np.random.uniform(0, 3), 2)
            waste_kg = max(0, waste_kg)
            rating = round(np.random.uniform(2.5, 5.0), 1)
            occupancy = round((attendance / 200) * 100 +
                              np.random.uniform(-5, 10), 1)
            occupancy = min(100, max(10, occupancy))
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "day_of_week": d.strftime("%A"),
                "meal": meal,
                "attendance": attendance,
                "planned_servings": planned,
                "waste_kg": waste_kg,
                "avg_rating": rating,
                "occupancy_pct": occupancy
            })
    return pd.DataFrame(rows)


df_mess = load_mess_data()

# ---------------- STREAK HELPERS ----------------


def get_streak(username):
    cursor.execute("SELECT * FROM streaks WHERE username=?", (username,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO streaks VALUES(?,0,0,?,0,0)",
            (username, str(date.today()))
        )
        conn.commit()
        return {"current": 0, "longest": 0, "total_visits": 0, "total_ratings": 0}
    return {
        "current": row[1],
        "longest": row[2],
        "last_active": row[3],
        "total_visits": row[4],
        "total_ratings": row[5]
    }


def update_visit_streak(username):
    today = str(date.today())
    s = get_streak(username)
    last = s.get("last_active", "")
    yesterday = str(date.today() - timedelta(days=1))

    if last == today:
        return  # already visited today

    if last == yesterday:
        new_streak = s["current"] + 1
    else:
        new_streak = 1

    longest = max(new_streak, s["longest"])
    total_visits = s["total_visits"] + 1

    cursor.execute("""
        INSERT INTO streaks(username, current_streak, longest_streak, last_active_date, total_visits, total_ratings)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(username) DO UPDATE SET
            current_streak=excluded.current_streak,
            longest_streak=excluded.longest_streak,
            last_active_date=excluded.last_active_date,
            total_visits=excluded.total_visits
    """, (username, new_streak, longest, today, total_visits, s["total_ratings"]))
    conn.commit()


def update_rating_streak(username):
    cursor.execute("""
        INSERT INTO streaks(username, current_streak, longest_streak, last_active_date, total_visits, total_ratings)
        VALUES(?,0,0,?,0,1)
        ON CONFLICT(username) DO UPDATE SET
            total_ratings = total_ratings + 1
    """, (username, str(date.today())))
    conn.commit()


def get_streak_badge(streak):
    if streak >= 30:
        return "🏆 Legend", "#FFD700"
    elif streak >= 14:
        return "💎 Diamond", "#00CFFF"
    elif streak >= 7:
        return "🔥 On Fire", "#FF6B35"
    elif streak >= 3:
        return "⚡ Rising", "#A8FF3E"
    elif streak >= 1:
        return "🌱 Starter", "#90EE90"
    else:
        return "😴 Inactive", "#888888"

# ---------------- PAGE CONFIG ----------------


st.set_page_config(
    page_title="MessPulse",
    page_icon="🍲",
    layout="wide"
)

# ---------------- LOGIN ----------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    st.markdown("""
    <style>
    .stApp {
        background:
        linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.45)),
        url("https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=2070&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        backdrop-filter: blur(12px);
    }
    .main-title {
        text-align: center;
        font-size: 70px;
        font-weight: 800;
        color: #FFD93D;
        text-shadow: 3px 3px 10px rgba(0,0,0,0.8);
    }
    .sub-title {
        text-align: center;
        font-size: 28px;
        color: white;
        text-shadow: 2px 2px 8px rgba(0,0,0,0.9);
        font-weight: 600;
    }
    label {
        color: white !important;
        font-size: 18px !important;
        font-weight: bold !important;
        text-shadow: 2px 2px 8px black;
    }
    .stTextInput input {
        color: black !important;
        font-size: 18px;
        font-weight: 600;
        background-color: rgba(255,255,255,0.95);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="main-title">🍲 MessPulse</div>
    <div class="sub-title">Smart Hostel Dining Experience ✨</div>
    """, unsafe_allow_html=True)

    auth_mode = st.radio("Select Option", ["Login", "Register"])
    username = st.text_input("👤 Username")
    room = st.text_input("🚪 Room Number")
    password = st.text_input("🔒 Password", type="password")

    if auth_mode == "Register":
        if st.button("Create Account"):
            cursor.execute("SELECT * FROM users WHERE username=?", (username,))
            if cursor.fetchone():
                st.error("Username already exists")
            else:
                cursor.execute("INSERT INTO users VALUES(?,?,?)",
                               (username, room, password))
                conn.commit()
                st.success("Account Created Successfully! Please Login.")

    if auth_mode == "Login":
        if st.button("Login"):
            cursor.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, password)
            )
            user = cursor.fetchone()
            if user:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid Username or Password")

    st.stop()

# ---------------- UPDATE STREAK ON VISIT ----------------

update_visit_streak(st.session_state.username)
streak_info = get_streak(st.session_state.username)
badge_label, badge_color = get_streak_badge(streak_info["current"])

# ---------------- CSS ----------------

st.markdown("""
<style>
.stApp {
    background:
    linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.45)),
    url("https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=2070&auto=format&fit=crop");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    backdrop-filter: blur(12px);
}
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background:
    linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.45)),
    url("https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=2070&auto=format&fit=crop");
    background-size: cover;
    background-position: center;
    filter: blur(8px);
    transform: scale(1.05);
    z-index: -1;
}
h1, h2, h3, p, label { color: white !important; }
[data-testid="stDataFrame"] {
    background-color: rgba(255,255,255,0.92);
    border-radius: 15px;
    padding: 10px;
}
.stButton button {
    background: linear-gradient(135deg,#ff4b4b,#ff7676);
    color: white;
    border-radius: 12px;
    border: none;
    padding: 10px 20px;
    font-weight: bold;
}
.stTextInput input,
.stTextArea textarea,
.stSelectbox select {
    background-color: rgba(255,255,255,0.9);
    color: black;
    border-radius: 10px;
}
[data-testid="stToast"] {
    background: rgba(0,0,0,0.8) !important;
    color: white !important;
    border-radius: 12px !important;
}
[data-testid="stToast"] * { color: white !important; font-weight: bold !important; }
div[data-testid="stAlert"] {
    background-color: rgba(0,0,0,0.75) !important;
    color: white !important;
    border-radius: 12px !important;
    font-weight: bold;
}
div[data-testid="stAlert"] p { color: white !important; font-size: 16px !important; }
.streak-card {
    background: rgba(0,0,0,0.55);
    border-radius: 18px;
    padding: 18px 24px;
    text-align: center;
    border: 2px solid rgba(255,255,255,0.15);
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------

st.markdown(f"""
<div style='text-align:center; padding-top:20px;'>
    <h1 style='font-size:60px;'>🍲 MessPulse</h1>
    <p style='font-size:22px;'>Welcome, {st.session_state.username} 👋</p>
    <p style='font-size:18px;'>Your daily companion for a better dining experience.</p>
</div>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown(f"""
    <div class='streak-card'>
        <div style='font-size:42px;'>{badge_label}</div>
        <div style='font-size:28px; font-weight:900; color:{badge_color};'>{streak_info['current']} Day Streak 🔥</div>
        <div style='font-size:14px; color:#ccc; margin-top:6px;'>Longest: {streak_info['longest']} days</div>
        <div style='font-size:14px; color:#ccc;'>Total Visits: {streak_info['total_visits']}</div>
        <div style='font-size:14px; color:#ccc;'>Ratings Given: {streak_info['total_ratings']}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Streak milestone messages
    s = streak_info["current"]
    if s == 0:
        st.info("Visit daily to start your streak! 🌱")
    elif s < 3:
        st.info(f"Keep going! {3 - s} more days to reach ⚡ Rising")
    elif s < 7:
        st.warning(f"Almost there! {7 - s} more days to reach 🔥 On Fire")
    elif s < 14:
        st.success(f"Awesome! {14 - s} more days to reach 💎 Diamond")
    elif s < 30:
        st.success(f"Incredible! {30 - s} more days to reach 🏆 Legend")
    else:
        st.success("You are a MessPulse LEGEND! 🏆")

    st.markdown("---")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.pop("username", None)
        st.rerun()

# ---------------- TABS ----------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🍽️ Weekly Menu",
    "⭐ Share Your Thoughts",
    "📊 Insights",
    "📡 Live Pulse",
    "🏅 Leaderboard"
])

# ---------------- TAB 1: MENU ----------------

with tab1:
    st.header("📋 Weekly Hostel Menu")

    menu_data = {
        "Meal": ["Breakfast", "Lunch", "Snacks", "Dinner"],
        "Monday":    ["Poha & Chai", "Dal Tadka & Rice", "Samosa", "Paneer Butter Masala"],
        "Tuesday":   ["Paratha", "Veg Biryani", "Biscuits", "Chicken Curry"],
        "Wednesday": ["Idli Sambhar", "Rajma Chawal", "Pakora", "Aloo Gobhi"],
        "Thursday":  ["Upma", "Chole Bhature", "Tea & Bun", "Mix Veg"],
        "Friday":    ["Dosa", "Egg Curry", "Sandwich", "Fish/Paneer Fry"],
        "Saturday":  ["Puri Bhaji", "Kadhai Paneer", "Maggi", "Jeera Rice"],
        "Sunday":    ["Pancakes", "Special Thali", "Cutlet", "Pasta"]
    }

    menu_df = pd.DataFrame(menu_data)

    # Highlight today's column
    today_name = datetime.today().strftime("%A")

    st.dataframe(menu_df, use_container_width=True, hide_index=True)

    if today_name in menu_data:
        today_menu = dict(zip(menu_data["Meal"], menu_data[today_name]))
        st.markdown(f"### 📅 Today's Menu — {today_name}")
        cols = st.columns(4)
        icons = ["☀️", "🍱", "🍪", "🌙"]
        for i, (meal_name, dish) in enumerate(today_menu.items()):
            with cols[i]:
                st.markdown(f"""
                <div style='background:rgba(255,255,255,0.1); border-radius:14px; padding:16px; text-align:center;'>
                    <div style='font-size:28px;'>{icons[i]}</div>
                    <div style='font-weight:bold; font-size:15px;'>{meal_name}</div>
                    <div style='font-size:14px; color:#FFD93D;'>{dish}</div>
                </div>
                """, unsafe_allow_html=True)

# ---------------- TAB 2: FEEDBACK ----------------

with tab2:
    st.header("⭐ Share Your Thoughts")

    # Show user's streak nudge
    if streak_info["total_ratings"] == 0:
        st.info("🎯 Rate your first meal to start earning streak points!")
    else:
        st.success(
            f"🏅 You've submitted {streak_info['total_ratings']} ratings! Keep it up for a higher badge.")

    c1, c2 = st.columns(2)

    with c1:
        meal = st.selectbox(
            "Meal",
            ["Breakfast", "Lunch", "Snacks", "Dinner"],
            key="meal_select"
        )

    with c2:
        rating = st.slider("Rating ⭐", 1, 5, 3, key="rating_slider")

    comment = st.text_area("Comment (optional)", key="comment_box")

    if st.button("Send Feedback 🚀"):
        today_str = str(date.today())
        cursor.execute(
            "INSERT INTO feedback(username, meal, rating, comment, submitted_date) VALUES(?,?,?,?,?)",
            (st.session_state.username, meal, rating, comment, today_str)
        )
        conn.commit()
        update_rating_streak(st.session_state.username)
        streak_info = get_streak(st.session_state.username)

        st.success(
            f"🔥 Feedback submitted! You now have {streak_info['total_ratings']} total ratings.")

        st.markdown("""
        <style>
        .fire {
            position: fixed;
            bottom: -50px;
            font-size: 40px;
            animation: floatUp 4s linear forwards;
            z-index: 9999;
        }
        .fire:nth-child(1) { left: 10%; }
        .fire:nth-child(2) { left: 30%; }
        .fire:nth-child(3) { left: 50%; }
        .fire:nth-child(4) { left: 70%; }
        .fire:nth-child(5) { left: 90%; }
        @keyframes floatUp {
            0% { transform: translateY(0); opacity: 1; }
            100% { transform: translateY(-800px); opacity: 0; }
        }
        </style>
        <div class="fire">🔥</div>
        <div class="fire">🔥</div>
        <div class="fire">🔥</div>
        <div class="fire">🔥</div>
        <div class="fire">🔥</div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📜 Recent Feedback from Everyone")

    cursor.execute(
        "SELECT username, meal, rating, comment, submitted_date FROM feedback ORDER BY id DESC LIMIT 10"
    )
    recent = cursor.fetchall()
    if recent:
        for row in recent:
            stars = "⭐" * row[2]
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.08); border-radius:12px; padding:12px; margin-bottom:8px;'>
                <b>{row[0]}</b> · {row[1]} · {stars} · <span style='color:#aaa; font-size:13px;'>{row[4]}</span><br>
                <span style='color:#eee;'>{row[3] if row[3] else "No comment"}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No feedback yet. Be the first!")

# ---------------- TAB 3: INSIGHTS ----------------

with tab3:
    st.header("📊 Smart Waste & Insights Dashboard")

    # --- LIVE METRICS FROM DATASET ---
    today_dow = datetime.today().strftime("%A")
    today_data = df_mess[df_mess["day_of_week"] == today_dow]
    if today_data.empty:
        today_data = df_mess.tail(4)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🍽️ Avg Attendance Today",
                  f"{int(today_data['attendance'].mean())}/meal")
    with col2:
        st.metric("♻️ Waste Today",
                  f"{round(today_data['waste_kg'].sum(), 1)} kg")
    with col3:
        st.metric("👥 Avg Occupancy",
                  f"{round(today_data['occupancy_pct'].mean(), 1)}%")
    with col4:
        st.metric("⭐ Avg Rating",
                  f"{round(today_data['avg_rating'].mean(), 1)}/5")

    st.markdown("---")

    # --- PREDICTION ---
    st.subheader("🔮 Tomorrow's Predicted Attendance")
    daily_avg = df_mess.groupby("date")["attendance"].mean().reset_index()
    daily_avg["day_num"] = range(1, len(daily_avg) + 1)
    X = daily_avg[["day_num"]].values
    y = daily_avg["attendance"].values
    model = LinearRegression().fit(X, y)
    predicted = int(model.predict(np.array([[len(daily_avg) + 1]]))[0])
    predicted_waste = round((200 - predicted) * 0.35, 1)
    pc1, pc2 = st.columns(2)
    with pc1:
        st.metric("📈 Predicted Attendance/Meal", predicted,
                  delta=f"{predicted - int(y[-1])} vs yesterday")
    with pc2:
        st.metric("🗑️ Estimated Waste Tomorrow", f"{predicted_waste} kg")

    st.markdown("---")

    # ============================================================
    # TIME FILTER HELPER
    # ============================================================
    def filter_df(df, period, meal_filter="All Meals", key_suffix=""):
        """Filter dataframe by time period and meal."""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        last_date = df["date"].max()

        if period == "Last 7 Days":
            df = df[df["date"] >= last_date - timedelta(days=6)]
        elif period == "Last 14 Days":
            df = df[df["date"] >= last_date - timedelta(days=13)]
        elif period == "Last 30 Days":
            df = df[df["date"] >= last_date - timedelta(days=29)]
        # "All Data" → no filter

        if meal_filter != "All Meals":
            df = df[df["meal"] == meal_filter]

        return df

    def time_meal_filter(section_key):
        """Render period + meal filter pills, return selections."""
        fc1, fc2 = st.columns([3, 2])
        with fc1:
            period = st.radio(
                "📅 Time Period",
                ["Last 7 Days", "Last 14 Days", "Last 30 Days", "All Data"],
                horizontal=True,
                key=f"period_{section_key}"
            )
        with fc2:
            meal_f = st.selectbox(
                "🍱 Meal Filter",
                ["All Meals", "Breakfast", "Lunch", "Snacks", "Dinner"],
                key=f"meal_{section_key}"
            )
        return period, meal_f

    # ============================================================
    # GRAPH 1 — WASTE TREND
    # ============================================================
    st.subheader("📉 Waste Trend")
    period_w, meal_w = time_meal_filter("waste")
    df_w = filter_df(df_mess, period_w, meal_w)

    if df_w.empty:
        st.warning("No data for this selection.")
    else:
        waste_trend = df_w.groupby("date")["waste_kg"].sum().reset_index()
        waste_trend.columns = ["Date", "Total Waste (kg)"]
        # Summary stat
        wc1, wc2, wc3 = st.columns(3)
        wc1.metric("Total Waste",
                   f"{round(waste_trend['Total Waste (kg)'].sum(), 1)} kg")
        wc2.metric(
            "Avg/Day", f"{round(waste_trend['Total Waste (kg)'].mean(), 1)} kg")
        wc3.metric(
            "Peak Day", f"{round(waste_trend['Total Waste (kg)'].max(), 1)} kg")
        st.area_chart(waste_trend.set_index("Date"))

    st.markdown("---")

    # ============================================================
    # GRAPH 2 — ATTENDANCE TREND
    # ============================================================
    st.subheader("🍱 Attendance Trend")
    period_a, meal_a = time_meal_filter("attendance")
    df_a = filter_df(df_mess, period_a, meal_a)

    if df_a.empty:
        st.warning("No data for this selection.")
    else:
        att_trend = df_a.groupby("date")["attendance"].mean().reset_index()
        att_trend.columns = ["Date", "Avg Attendance"]
        att_trend["Date"] = att_trend["Date"].astype(str)
        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("Avg Attendance",
                   f"{int(att_trend['Avg Attendance'].mean())}/meal")
        ac2.metric("Peak Day", f"{int(att_trend['Avg Attendance'].max())}")
        ac3.metric("Lowest Day", f"{int(att_trend['Avg Attendance'].min())}")
        st.bar_chart(att_trend.set_index("Date"))

    st.markdown("---")

    # ============================================================
    # GRAPH 3 — RATINGS TREND
    # ============================================================
    st.subheader("⭐ Ratings Trend")
    period_r, meal_r = time_meal_filter("ratings")
    df_r = filter_df(df_mess, period_r, meal_r)

    if df_r.empty:
        st.warning("No data for this selection.")
    else:
        rat_trend = df_r.groupby("date")["avg_rating"].mean().reset_index()
        rat_trend.columns = ["Date", "Avg Rating"]
        rat_trend["Date"] = rat_trend["Date"].astype(str)
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric(
            "Avg Rating", f"{round(rat_trend['Avg Rating'].mean(), 2)}/5")
        rc2.metric("Best Day", f"{round(rat_trend['Avg Rating'].max(), 2)}/5")
        rc3.metric("Worst Day", f"{round(rat_trend['Avg Rating'].min(), 2)}/5")
        st.line_chart(rat_trend.set_index("Date"))

    st.markdown("---")

    # ============================================================
    # GRAPH 4 — MEAL BREAKDOWN (by meal type, filtered by period)
    # ============================================================
    st.subheader("🔍 Meal-wise Breakdown")
    period_mb, _ = time_meal_filter("breakdown")
    df_mb = filter_df(df_mess, period_mb, "All Meals")

    if not df_mb.empty:
        mb1, mb2 = st.columns(2)
        with mb1:
            meal_att = df_mb.groupby("meal")["attendance"].mean().reset_index()
            meal_att.columns = ["Meal", "Avg Attendance"]
            st.caption("Avg Attendance per Meal")
            st.bar_chart(meal_att.set_index("Meal"))
        with mb2:
            meal_wst = df_mb.groupby("meal")["waste_kg"].mean().reset_index()
            meal_wst.columns = ["Meal", "Avg Waste (kg)"]
            st.caption("Avg Waste per Meal")
            st.bar_chart(meal_wst.set_index("Meal"))

    st.markdown("---")

    # ============================================================
    # GRAPH 5 — DAY OF WEEK PATTERNS
    # ============================================================
    st.subheader("📆 Day-of-Week Patterns")
    period_d, meal_d = time_meal_filter("dayofweek")
    df_d = filter_df(df_mess, period_d, meal_d)

    if not df_d.empty:
        day_order = ["Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Saturday", "Sunday"]
        dow_data = df_d.groupby("day_of_week").agg(
            Attendance=("attendance", "mean"),
            Waste=("waste_kg", "mean"),
            Rating=("avg_rating", "mean")
        ).reindex(day_order).dropna().reset_index()
        dow_data.columns = ["Day", "Avg Attendance",
                            "Avg Waste (kg)", "Avg Rating"]

        dc1, dc2 = st.columns(2)
        with dc1:
            st.caption("Attendance by Day")
            st.bar_chart(dow_data.set_index("Day")[["Avg Attendance"]])
        with dc2:
            st.caption("Waste by Day")
            st.bar_chart(dow_data.set_index("Day")[["Avg Waste (kg)"]])

    st.markdown("---")

    # --- ATTENDANCE COMMITMENT ---
    st.subheader("🙋 Meal Attendance Commitment")
    st.write("Are you dining with us for the next meal? Help the kitchen plan!")

    if "commitment" not in st.session_state:
        st.session_state.commitment = "Not Decided"

    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("✅ I'm Coming"):
            st.session_state.commitment = "Attending"
            today_str = str(date.today())
            now_meal = ["Breakfast", "Lunch", "Snacks",
                        "Dinner"][min(datetime.now().hour // 6, 3)]
            cursor.execute(
                "INSERT OR REPLACE INTO checkins VALUES(?,?,?,?)",
                (st.session_state.username, today_str, now_meal, "Attending")
            )
            conn.commit()
            st.toast("Status updated: Attending", icon="🍲")

        if st.button("❌ Skip Meal"):
            st.session_state.commitment = "Skipping"
            st.toast("Status updated: Skipping", icon="♻️")

    with c2:
        if st.session_state.commitment == "Attending":
            st.success(
                f"**Status:** {st.session_state.username}, your plate is reserved! See you at the mess.")
        elif st.session_state.commitment == "Skipping":
            st.warning(
                "**Status:** Thanks! You just helped save ~350g of food.")
        else:
            st.info("**Status:** Please select your attendance.")

    cursor.execute(
        "SELECT COUNT(*) FROM checkins WHERE checkin_date=? AND status='Attending'",
        (str(date.today()),)
    )
    committed_today = cursor.fetchone()[0]
    waste_saved = round((200 - committed_today) * 0.35,
                        2) if committed_today < 200 else 0

    mc1, mc2 = st.columns(2)
    with mc1:
        st.metric("✅ Confirmed Attendees Today", committed_today)
    with mc2:
        st.metric("🍃 Waste Preventable", f"{waste_saved} kg")

# ---------------- TAB 4: LIVE PULSE ----------------

with tab4:
    st.header("📡 Live Mess Density")
    st.write("Live occupancy estimated from today's dataset patterns.")

    # Use today's occupancy from dataset
    now_hour = datetime.now().hour
    if 7 <= now_hour <= 9:
        current_meal = "Breakfast"
    elif 12 <= now_hour <= 14:
        current_meal = "Lunch"
    elif 16 <= now_hour <= 18:
        current_meal = "Snacks"
    elif 19 <= now_hour <= 21:
        current_meal = "Dinner"
    else:
        current_meal = "Lunch"  # off-peak default

    meal_occupancy = df_mess[
        (df_mess["day_of_week"] == today_dow) &
        (df_mess["meal"] == current_meal)
    ]["occupancy_pct"]

    if meal_occupancy.empty:
        occupancy_rate = 65.0
    else:
        occupancy_rate = round(meal_occupancy.mean(), 1)

    live_pings = int((occupancy_rate / 100) * 150)
    max_capacity = 150

    if occupancy_rate < 40:
        status_msg = "Low Crowd — Direct Entry 🟢"
        wait_est = "1-3 mins"
        color = "green"
    elif occupancy_rate < 75:
        status_msg = "Moderate Crowd — Moving 🟡"
        wait_est = "7-10 mins"
        color = "#FFD93D"
    else:
        status_msg = "High Crowd — Busy 🔴"
        wait_est = "18-22 mins"
        color = "#FF4B4B"

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"""
        <div style="background-color:rgba(255,255,255,0.05); padding:20px; border-radius:15px; border-left: 10px solid {color};">
            <h3 style="margin:0;">{status_msg}</h3>
            <p style="font-size:18px; margin-top:10px;">Occupancy: <b>{int(occupancy_rate)}%</b></p>
            <p style="font-size:14px; color:#ccc;">Current Meal Period: {current_meal}</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.progress(min(occupancy_rate / 100, 1.0))

    with col2:
        st.metric("Estimated Wait", wait_est,
                  delta="-2 mins" if occupancy_rate < 50 else "+5 mins")
        st.metric("Est. Active People", f"{live_pings}")

    st.markdown("---")

    st.subheader("📍 Manual Check-in")
    st.write("Are you currently at the mess?")
    if st.button("I'm here! 🙋"):
        st.success(
            "Thanks! Your ping helps make wait-time more accurate for others.")

    st.markdown("---")

    # ============================================================
    # OCCUPANCY TREND with time filter
    # ============================================================
    st.subheader("📈 Occupancy Trend")
    ot_c1, ot_c2 = st.columns([3, 2])
    with ot_c1:
        period_ot = st.radio(
            "📅 Time Period",
            ["Last 7 Days", "Last 14 Days", "Last 30 Days", "All Data"],
            horizontal=True,
            key="period_occ_trend"
        )
    with ot_c2:
        meal_ot = st.selectbox(
            "🍱 Meal Filter",
            ["All Meals", "Breakfast", "Lunch", "Snacks", "Dinner"],
            key="meal_occ_trend"
        )

    df_ot = df_mess.copy()
    df_ot["date"] = pd.to_datetime(df_ot["date"])
    last_date_ot = df_ot["date"].max()
    if period_ot == "Last 7 Days":
        df_ot = df_ot[df_ot["date"] >= last_date_ot - timedelta(days=6)]
    elif period_ot == "Last 14 Days":
        df_ot = df_ot[df_ot["date"] >= last_date_ot - timedelta(days=13)]
    elif period_ot == "Last 30 Days":
        df_ot = df_ot[df_ot["date"] >= last_date_ot - timedelta(days=29)]
    if meal_ot != "All Meals":
        df_ot = df_ot[df_ot["meal"] == meal_ot]

    if not df_ot.empty:
        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Avg Occupancy",
                   f"{round(df_ot['occupancy_pct'].mean(), 1)}%")
        oc2.metric("Peak", f"{round(df_ot['occupancy_pct'].max(), 1)}%")
        oc3.metric("Lowest", f"{round(df_ot['occupancy_pct'].min(), 1)}%")
        occ_trend = df_ot.groupby("date")["occupancy_pct"].mean().reset_index()
        occ_trend.columns = ["Date", "Avg Occupancy %"]
        st.line_chart(occ_trend.set_index("Date"))

    st.markdown("---")

    # ============================================================
    # OCCUPANCY BY MEAL with time filter
    # ============================================================
    st.subheader("📊 Avg Occupancy by Meal")
    om_c1, _ = st.columns([3, 2])
    with om_c1:
        period_om = st.radio(
            "📅 Time Period",
            ["Last 7 Days", "Last 14 Days", "Last 30 Days", "All Data"],
            horizontal=True,
            key="period_occ_meal"
        )

    df_om = df_mess.copy()
    df_om["date"] = pd.to_datetime(df_om["date"])
    last_date_om = df_om["date"].max()
    if period_om == "Last 7 Days":
        df_om = df_om[df_om["date"] >= last_date_om - timedelta(days=6)]
    elif period_om == "Last 14 Days":
        df_om = df_om[df_om["date"] >= last_date_om - timedelta(days=13)]
    elif period_om == "Last 30 Days":
        df_om = df_om[df_om["date"] >= last_date_om - timedelta(days=29)]

    if not df_om.empty:
        occ_by_meal = df_om.groupby(
            "meal")["occupancy_pct"].mean().reset_index()
        occ_by_meal.columns = ["Meal", "Avg Occupancy %"]
        st.bar_chart(occ_by_meal.set_index("Meal"))

# ---------------- TAB 5: LEADERBOARD ----------------

with tab5:
    st.header("🏅 Streak Leaderboard")
    st.write("Top users by current streak and total engagement!")

    cursor.execute("""
        SELECT username, current_streak, longest_streak, total_visits, total_ratings
        FROM streaks
        ORDER BY current_streak DESC, total_ratings DESC
        LIMIT 20
    """)
    lb_rows = cursor.fetchall()

    if lb_rows:
        rank_emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 17
        for i, row in enumerate(lb_rows):
            uname, cur_s, long_s, visits, ratings = row
            badge, bcolor = get_streak_badge(cur_s)
            is_me = "← You!" if uname == st.session_state.username else ""
            st.markdown(f"""
            <div style='background:rgba(255,255,255,{"0.15" if is_me else "0.07"}); border-radius:14px;
                        padding:14px 20px; margin-bottom:8px;
                        border: {"2px solid #FFD93D" if is_me else "1px solid rgba(255,255,255,0.1)"};'>
                <span style='font-size:22px;'>{rank_emojis[i]}</span>
                <b style='font-size:18px; margin-left:8px;'>{uname}</b>
                <span style='color:{bcolor}; margin-left:10px;'>{badge}</span>
                <span style='color:#FFD93D; font-weight:bold; margin-left:10px;'>{cur_s}🔥 streak</span>
                <span style='color:#aaa; font-size:13px; margin-left:10px;'>Best: {long_s} | Visits: {visits} | Ratings: {ratings}</span>
                <b style='color:#FFD93D; float:right;'>{is_me}</b>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No users on the board yet. Start visiting to appear here!")

# ---------------- FOOTER ----------------

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align:center; color:white;'>
    Made with ❤️ by MessPulse Team • 2026
</div>
""", unsafe_allow_html=True)
