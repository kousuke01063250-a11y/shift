import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ページ設定（管理者用）
st.set_page_config(page_title="シフト確認ダッシュボード", layout="wide")

# ==========================================
# 🔒 簡易パスワード認証機能
# ==========================================
def check_password():
    """正しいパスワードが入力されたらTrueを返す"""
    def password_entered():
        """入力されたパスワードを検証する内部関数"""
        # 🔑 お好きなパスワードに変更してください（現在は "admin123" になっています）
        if st.session_state["password"] == "admin123":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # セキュリティのため入力値を消去
        else:
            st.session_state["password_correct"] = False

    # すでに認証済みの場合はスキップ
    if st.session_state.get("password_correct", False):
        return True

    # パスワード入力フォームの画面を表示
    st.title("🔒 管理者認証")
    st.warning("このページにアクセスするには管理用パスワードが必要です。")
    st.text_input(
        "パスワードを入力してください", 
        type="password", 
        on_change=password_entered, 
        key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 パスワードが違います。もう一度入力してください。")
        
    return False

# パスワードチェックが通らない場合は、これ以降のコードを実行せずに終了する
if not check_password():
    st.stop()

# ==========================================
# 🔑 Notion基本設定（ここからは認証が通った場合のみ実行されます）
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de880279373de917797c6ff"  

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.title("📊 シフト確認ダッシュボード（管理者用）")

# ------------------------------------------
# 💡 日付計算ロジック
# ------------------------------------------
today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)

week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# ------------------------------------------
# シフトデータの読み込みと可視化
# ------------------------------------------
parsed_records = []
query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
response = requests.post(query_url, headers=headers)

if response.status_code == 200:
    notion_data = response.json()
    for page in notion_data.get("results", []):
        props = page.get("properties", {})
        try:
            r_name = props["スタッフ"]["title"][0]["text"]["content"]
            r_start = props["開始"]["rich_text"][0]["text"]["content"]
            r_end = props["終了"]["rich_text"][0]["text"]["content"]
            r_shift = props["シフト"]["rich_text"][0]["text"]["content"]
            
            if r_start != "-" and r_end != "-":
                r_date = r_start.split(" ")[0]
                parsed_records.append({
                    "スタッフ": r_name,
                    "日付": r_date,
                    "シフト": r_shift,
                    "開始": r_start,
                    "終了": r_end
                })
        except (KeyError, IndexError):
            continue

if parsed_records:
    df_all = pd.DataFrame(parsed_records)
    
    st.subheader("曜日別 タイムライン確認")
    selected_day_index = st.selectbox("確認したい曜日を選択してください", range(7), format_func=lambda x: f"{target_dates[x]} ({week_days[x]}曜日)")
    selected_date_str = target_dates[selected_day_index]
    
    df_filtered = df_all[df_all["日付"] == selected_date_str]
    
    if not df_filtered.empty:
        try:
            fig = px.timeline(
                df_filtered, 
                x_start="開始", 
                x_end="終了", 
                y="スタッフ",      
                color="スタッフ",    
                text="スタッフ",     
                title=f"📅 {selected_date_str} ({week_days[selected_day_index]}曜日) の出勤可能時間"
            )
            fig.update_yaxes(autorange="reversed") 
            fig.update_layout(xaxis=dict(title="時間帯", tickformat="%H:%M"), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("該当日の提出データ一覧")
            st.dataframe(df_filtered[["スタッフ", "シフト"]], use_container_width=True)
            
        except Exception as e:
            st.error(f"タイムラインの描画中にエラーが発生しました: {e}")
    else:
        st.info(f"選択された日（{selected_date_str}）に出勤可能なスタッフはいません。")
else:
    st.info("Notionのデータベース内に有効なシフトデータが見つかりません。")

st.markdown("---")
st.link_button("Notionで直接生データを確認する", f"https://app.notion.com/p/{DATABASE_ID}")
