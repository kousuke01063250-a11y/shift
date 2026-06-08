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
SHIFT_DB_ID = "376f6a7e7de880279373de917797c6ff"      # シフト保存用DB
STAFF_DB_ID = "379f6a7e7de880a9ab76e859e099c7e0"      # ✨新設：スタッフ一覧用DB

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ------------------------------------------
# 🧹 【自動クレンジング機能】3週間前（21日前）より古いデータをアーカイブ
# ------------------------------------------
def auto_clean_past_data():
    query_url = f"https://api.notion.com/v1/databases/{SHIFT_DB_ID}/query"
    res = requests.post(query_url, headers=headers)
    
    if res.status_code == 200:
        notion_data = res.json()
        
        three_weeks_ago = datetime.today() - timedelta(days=21)
        threshold_date_str = three_weeks_ago.strftime("%Y-%m-%d")
        
        cleaned_count = 0
        for page in notion_data.get("results", []):
            page_id = page.get("id")
            props = page.get("properties", {})
            try:
                r_start = props["開始"]["rich_text"][0]["text"]["content"]
                if r_start != "-":
                    record_date = r_start.split(" ")[0]
                    if record_date < threshold_date_str:
                        update_url = f"https://api.notion.com/v1/pages/{page_id}"
                        requests.patch(update_url, headers=headers, json={"archived": True})
                        cleaned_count += 1
            except (KeyError, IndexError):
                continue
        
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

# 最新シフトデータの読み込み
parsed_records = []
query_url = f"https://api.notion.com/v1/databases/{SHIFT_DB_ID}/query"
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


# ==========================================
# 👥 ✨【新設】GUIスタッフマスター管理機能
# ==========================================
st.markdown("---")
st.header("👥 スタッフアカウント管理")

# 1. 現在登録されているスタッフをNotionから取得
staff_query_url = f"https://api.notion.com/v1/databases/{STAFF_DB_ID}/query"
staff_res = requests.post(staff_query_url, headers=headers, json={"sorts": [{"property": "名前", "direction": "ascending"}]})

current_staff = {}
if staff_res.status_code == 200:
    for page in staff_res.json().get("results", []):
        page_id = page.get("id")
        try:
            name_text = page["properties"]["名前"]["title"][0]["text"]["content"]
            current_staff[name_text] = page_id
        except (KeyError, IndexError):
            continue

# 2. 画面への表示と操作
col_add, col_del = st.columns(2)

with col_add:
    st.subheader("➕ スタッフの新規追加")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：高部 光佑")
    if st.button("➕ このスタッフを追加する", use_container_width=True):
        if not new_staff_name:
            st.error("氏名を入力してください。")
        elif new_staff_name in current_staff:
            st.warning(f"「{new_staff_name}」さんは既に登録されています。")
        else:
            # NotionのスタッフDBへ書き込み
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": STAFF_DB_ID},
                "properties": {
                    "名前": {"title": [{"text": {"content": new_staff_name}}]}
                }
            }
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                st.success(f"🎉 「{new_staff_name}」さんをマスターに登録しました！")
                st.rerun()
            else:
                st.error("Notionへの追加に失敗しました。")

with col_del:
    st.subheader("🗑️ スタッフの削除")
    if current_staff:
        del_target = st.selectbox("削除するスタッフを選択してください", list(current_staff.keys()))
        if st.button("🗑️ このスタッフを削除する", use_container_width=True):
            target_page_id = current_staff[del_target]
            # Notionの該当ページをアーカイブ（ごみ箱へ）
            archive_url = f"https://api.notion.com/v1/pages/{target_page_id}"
            res = requests.patch(archive_url, headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_target}」さんの登録を削除しました。")
                st.rerun()
            else:
                st.error("Notionからの削除に失敗しました。")
    else:
        st.info("現在、登録されているスタッフはいません。")


st.markdown("---")
st.link_button("Notionで直接生データを確認する", f"https://app.notion.com/p/{SHIFT_DB_ID}")
