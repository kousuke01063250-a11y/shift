import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ページ設定（管理者用）
st.set_page_config(page_title="シフト確認ダッシュボード", layout="wide")

# ==========================================
# 🔒 確実なパスワード認証機能
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def check_password():
    """正しいパスワードが入力されたらTrueを返す"""
    if st.session_state["password_correct"]:
        return True

    st.title("🔒 管理者認証")
    st.warning("このページにアクセスするには管理用パスワードが必要です。")
    
    input_password = st.text_input("パスワードを入力してください", type="password")
    
    if input_password:
        if input_password == "admin123":
            st.session_state["password_correct"] = True
            st.rerun() 
        else:
            st.error("😕 パスワードが違います。もう一度入力してください。")
            
    return False

if not check_password():
    st.stop()

# ==========================================
# 🔑 Notion基本設定
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de880279373de917797c6ff"  

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ------------------------------------------
# 🧹 【自動クレンジング機能】3週間前（21日前）より古いデータをアーカイブ
# ------------------------------------------
def auto_clean_past_data():
    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    res = requests.post(query_url, headers=headers)
    
    if res.status_code == 200:
        notion_data = res.json()
        
        # 💡 今日から数えて21日前（3週間前）の日付の基準線（しきい値）を計算
        three_weeks_ago = datetime.today() - timedelta(days=21)
        threshold_date_str = three_weeks_ago.strftime("%Y-%m-%d")
        
        cleaned_count = 0
        
        for page in notion_data.get("results", []):
            page_id = page.get("id")
            props = page.get("properties", {})
            try:
                r_start = props["開始"]["rich_text"][0]["text"]["content"]
                if r_start != "-":
                    # 「2026-06-15 09:00」から日付部分だけを抽出
                    record_date = r_start.split(" ")[0]
                    
                    # 💡 記録された日付が、3週間前の基準日よりもさらに古い（過去の）場合のみアーカイブ
                    if record_date < threshold_date_str:
                        update_url = f"https://api.notion.com/v1/pages/{page_id}"
                        requests.patch(update_url, headers=headers, json={"archived": True})
                        cleaned_count += 1
            except (KeyError, IndexError):
                continue
        
        # クレンジングが行われた場合、管理者に右下ポップアップで通知
        if cleaned_count > 0:
            st.toast(f"🧹 3週間以上前の古いデータ {cleaned_count} 件を自動アーカイブしました。")

# 管理画面が開かれた瞬間に自動実行
auto_clean_past_data()

# ==========================================
# 📊 ここからダッシュボードの描画
# ==========================================
st.title("📊 シフト確認ダッシュボード（管理者用）")

# 日付計算ロジック
today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)

week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# 最新データの読み込み
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
