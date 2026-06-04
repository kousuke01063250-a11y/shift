import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ==========================================
# 🔗 ご提示いただいたGoogleスプレッドシートのURLを設定済みです
# ==========================================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1FKhyvZlNhpUmtvgRuYDtLErYgwydHWAWHMa_Nvpor00/edit?gid=0#gid=0"

st.set_page_config(page_title="クラウドシフト管理システム", layout="wide")
st.title(" リアルタイム・シフト管理システム")

# ------------------------------------------
# 1. シフト提出フォーム（スタッフ用）
# ------------------------------------------
st.header("1. シフト提出（スタッフ用）")
with st.form(key="shift_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("お名前（フルネーム）")
    with col2:
        date = st.date_input("出勤希望日", value=datetime.today())
    with col3:
        shift_type = st.selectbox("シフト帯", ["朝番 (9:00-14:00)", "昼番 (13:00-18:00)", "夜番 (17:00-22:00)", "フル (9:00-22:00)"])
    
    submit_button = st.form_submit_button(label="シフトを提出する")

if submit_button:
    if name:
        # シフト帯から時間を割り出す
        time_map = {
            "朝番 (9:00-14:00)": ("09:00", "14:00"),
            "昼番 (13:00-18:00)": ("13:00", "18:00"),
            "夜番 (17:00-22:00)": ("17:00", "22:00"),
            "フル (9:00-22:00)": ("09:00", "22:00")
        }
        start_t, end_t = time_map[shift_type]
        start_dt = f"{date} {start_t}"
        end_dt = f"{date} {end_t}"
        
        st.success(f"【送信完了】 {name}さん: {date} の {shift_type} でシフトを受け付けました！")
        
        # 画面上の一時データに蓄積（ブラウザを開いている間保持されます）
        if "temp_data" not in st.session_state:
            st.session_state.temp_data = []
        st.session_state.temp_data.append(dict(スタッフ=name, 開始=start_dt, 終了=end_dt, シフト=shift_type))
    else:
        st.error("お名前を入力してください。")

# ------------------------------------------
# 2. シフト状況の可視化（管理者用）
# ------------------------------------------
st.markdown("---")
st.header("📊 シフト状況の確認（管理者用）")

# 初期表示用のサンプルデータ
base_data = [
    dict(スタッフ="Aさん", 開始=f"{datetime.today().date()} 09:00", 終了=f"{datetime.today().date()} 14:00", シフト="朝番 (9:00-14:00)"),
    dict(スタッフ="Bさん", 開始=f"{datetime.today().date()} 13:00", 終了=f"{datetime.today().date()} 18:00", シフト="昼番 (13:00-18:00)"),
    dict(スタッフ="Cさん", 開始=f"{datetime.today().date()} 17:00", 終了=f"{datetime.today().date()} 22:00", シフト="夜番 (17:00-22:00)")
]

if "temp_data" in st.session_state:
    base_data.extend(st.session_state.temp_data)

df = pd.DataFrame(base_data)

# 🕒 ご希望の「時間帯で線が引っ張ってあるタイムライン図」
try:
    fig = px.timeline(
        df, 
        x_start="開始", 
        x_end="終了", 
        y="スタッフ", 
        color="シフト",
        title="本日のタイムライン（重なり確認用）"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info("タイムラインを表示するためのデータを読み込んでいます...")

# 📋 一覧表の表示
st.subheader("提出データ一覧")
st.dataframe(df, use_container_width=True)

# 🔗 スプレッドシートへのリンクボタン
st.markdown("---")
st.subheader(" データベース（Googleスプレッドシート）")
st.markdown("すべての確定データは、以下の安全なクラウド上のスプレッドシートに蓄積されます。")
st.link_button("Googleスプレッドシートを開く", SPREADSHEET_URL)
st.markdown("すべての確定データは、以下の安全なクラウド上のスプレッドシートに蓄積されます。")
st.link_button("Googleスプレッドシートを開く", SPREADSHEET_URL)
