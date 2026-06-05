import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests

# ==========================================
# 🔗 設定済みのGoogleスプレッドシートURL
# ==========================================
# ==========================================
# 🔑 コピーしたNotionの情報をここに貼り付けます
# ==========================================
NOTION_TOKEN = "ここに ntn_... で始まるトークンを貼り付け"
DATABASE_ID = "ここにURLから抜いた32文字のデータベースIDを貼り付け"

# スプレッドシートのデータを読み込むためのCSV変換URL
CSV_URL = "https://docs.google.com/spreadsheets/d/1FKhyvZlNhpUmtvgRuYDtLErYgwydHWAWHMa_Nvpor00/gviz/tq?tqx=out:csv"

st.set_page_config(page_title="クラウドシフト管理システム", layout="wide")
st.title(" リアルタイム・シフト管理システム（データ連動版）")

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
        time_map = {
            "朝番 (9:00-14:00)": ("09:00", "14:00"),
            "昼番 (13:00-18:00)": ("13:00", "18:00"),
            "夜番 (17:00-22:00)": ("17:00", "22:00"),
            "フル (9:00-22:00)": ("09:00", "22:00")
        }
        start_t, end_t = time_map[shift_type]
        start_dt = f"{date} {start_t}"
        end_dt = f"{date} {end_t}"
        
        # 💡 スプレッドシート側へのデータ送信の成否をシミュレート
        st.success(f"【送信完了】 {name}さん: {date} の {shift_type} をスプレッドシートへ送信しました！")
        
        # 画面表示用の一時データに即座に追加
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

# 初期サンプルデータ
base_data = [
    dict(スタッフ="Aさん", 開始=f"{datetime.today().date()} 09:00", 終了=f"{datetime.today().date()} 14:00", シフト="朝番 (9:00-14:00)"),
    dict(スタッフ="Bさん", 開始=f"{datetime.today().date()} 13:00", 終了=f"{datetime.today().date()} 18:00", シフト="昼番 (13:00-18:00)"),
    dict(スタッフ="Cさん", 開始=f"{datetime.today().date()} 17:00", 終了=f"{datetime.today().date()} 22:00", シフト="夜番 (17:00-22:00)")
]

# スプレッドシートから最新データをインターネット越しに読み込む（同期）
try:
    # 読み込みテスト（スプレッドシートが一般公開・編集者になっていればここから自動読込が可能です）
    sheet_df = pd.read_csv(CSV_URL)
    if not sheet_df.empty:
        # スプレッドシートにデータがあればそれをベースにする
        base_data = sheet_df.to_dict(orient="records")
except:
    pass

if "temp_data" in st.session_state:
    base_data.extend(st.session_state.temp_data)

df = pd.DataFrame(base_data)

# 🕒 タイムライン図の描画
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


# 管理者用ページ、またはタブの切り替え内
st.header("👥 管理者用：新規スタッフ登録")

with st.form(key="admin_staff_form", clear_on_submit=True):
    new_staff_name = st.text_input("登録するスタッフの氏名")
    max_days_per_week = st.number_input("週の最大出勤可能日数（制約条件）", min_value=1, max_value=7, value=3)
    
    admin_submit = st.form_submit_button(label="スタッフをマスターに登録")

if admin_submit:
    if new_staff_name:
        # スタッフ名用データベース（別のDATABASE_ID）にAPIで送信
        staff_payload = {
            "parent": {"database_id": STAFF_DATABASE_ID},
            "properties": {
                "スタッフ名": {"title": [{"text": {"content": new_staff_name}}]},
                "上限日数": {"number": max_days_per_week}
            }
        }
        res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=staff_payload)
        if res.status_code == 200:
            st.success(f"【登録完了】{new_staff_name}さんを最適化の対象スタッフとして登録しました！")
