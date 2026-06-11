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
SHIFT_DB_ID = "376f6a7e7de880279373de917797c6ff"      # 1. シフト保存用DB
STAFF_DB_ID = "379f6a7e7de880a9ab76e859e099c7e0"      # 2. スタッフ一覧用DB
POSITION_DB_ID = "37cf6a7e7de88097847ac00582111279"   # 3. ポジション一覧用DB

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ------------------------------------------
# 🧹 【自動クレンジング機能】3週間前のデータを自動アーカイブ
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
            try:
                r_start = page["properties"]["開始"]["rich_text"][0]["text"]["content"]
                if r_start != "-":
                    record_date = r_start.split(" ")[0]
                    if record_date < threshold_date_str:
                        update_url = f"https://api.notion.com/v1/pages/{page_id}"
                        requests.patch(update_url, headers=headers, json={"archived": True})
                        cleaned_count += 1
            except (KeyError, IndexError):
                continue
        if cleaned_count > 0:
            st.toast(f"🧹 古いデータ {cleaned_count} 件を自動アーカイブしました。")

auto_clean_past_data()

# ==========================================
# 📊 シフト確認ダッシュボード
# ==========================================
st.title("📊 シフト確認ダッシュボード（管理者用）")

today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)
week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

parsed_records = []
query_url = f"https://api.notion.com/v1/databases/{SHIFT_DB_ID}/query"
response = requests.post(query_url, headers=headers)

if response.status_code == 200:
    for page in response.json().get("results", []):
        props = page.get("properties", {})
        try:
            r_name = props["スタッフ"]["title"][0]["text"]["content"]
            r_start = props["開始"]["rich_text"][0]["text"]["content"]
            r_end = props["終了"]["rich_text"][0]["text"]["content"]
            r_shift = props["シフト"]["rich_text"][0]["text"]["content"]
            if r_start != "-" and r_end != "-":
                parsed_records.append({
                    "スタッフ": r_name, "日付": r_start.split(" ")[0], "シフト": r_shift, "開始": r_start, "終了": r_end
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
            fig = px.timeline(df_filtered, x_start="開始", x_end="終了", y="スタッフ", color="スタッフ", text="スタッフ", title=f"📅 {selected_date_str} の出勤可能時間")
            fig.update_yaxes(autorange="reversed") 
            fig.update_layout(xaxis=dict(title="時間帯", tickformat="%H:%M"), showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_filtered[["スタッフ", "シフト"]], use_container_width=True)
        except Exception as e:
            st.error(f"エラー: {e}")
    else:
        st.info(f"選択された日（{selected_date_str}）に出勤可能なスタッフはいません。")
else:
    st.info("有効なシフトデータが見つかりません。")

st.markdown("---")

# ==========================================
# 🛠️ ポジション（マスター）管理
# ==========================================
st.header("🛠️ ポジション（マスター）管理")

pos_query_url = f"https://api.notion.com/v1/databases/{POSITION_DB_ID}/query"
pos_res = requests.post(pos_query_url, headers=headers)
current_positions = {}
if pos_res.status_code == 200:
    for page in pos_res.json().get("results", []):
        page_id = page.get("id")
        try:
            pos_text = page["properties"]["ポジション名"]["title"][0]["text"]["content"]
            current_positions[pos_text] = page_id
        except (KeyError, IndexError):
            continue

col_p1, col_p2 = st.columns(2)
with col_p1:
    new_pos_name = st.text_input("🎨 新しいポジション名を入力", placeholder="例：焼き場、レジ、ホール")
    if st.button("➕ ポジションを新規追加する", use_container_width=True):
        if new_pos_name and new_pos_name not in current_positions:
            res = requests.post("https://api.notion.com/v1/pages", headers=headers, json={
                "parent": {"database_id": POSITION_DB_ID},
                "properties": {"ポジション名": {"title": [{"text": {"content": new_pos_name}}]}}
            })
            if res.status_code == 200:
                st.success(f"🎉 ポジション「{new_pos_name}」を追加しました！")
                st.rerun()
        elif new_pos_name in current_positions:
            st.warning("そのポジションは既に存在します。")

with col_p2:
    if current_positions:
        del_pos_target = st.selectbox("🗑️ 削除するポジションを選択", list(current_positions.keys()))
        if st.button("🗑️ 選択したポジションを削除", use_container_width=True):
            res = requests.patch(f"https://api.notion.com/v1/pages/{current_positions[del_pos_target]}", headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_pos_target}」を削除しました。")
                st.rerun()
    else:
        st.info("登録されているポジションがありません。")

st.markdown("---")

# ==========================================
# 👥 スタッフアカウント管理（美しく2列に分離版）
# ==========================================
st.header("👥 スタッフアカウント管理")

staff_query_url = f"https://api.notion.com/v1/databases/{STAFF_DB_ID}/query"
staff_res = requests.post(staff_query_url, headers=headers)
current_staff = {}
if staff_res.status_code == 200:
    for page in staff_res.json().get("results", []):
        page_id = page.get("id")
        try:
            # 💡 名前の列からそのまま純粋な名前を取得
            name_text = page["properties"]["名前"]["title"][0]["text"]["content"]
            current_staff[name_text] = page_id
        except (KeyError, IndexError):
            continue

col_s1, col_s2 = st.columns(2)
with col_s1:
    st.subheader("➕ スタッフの新規追加（複数ポジション設定可）")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：高部 光佑", key="s_add_name")
    selected_skills = st.multiselect("担当できるポジションをすべて選択してください（複数可）", list(current_positions.keys()))
    
    if st.button("➕ このスタッフを追加する", use_container_width=True, key="s_add_btn"):
        if not new_staff_name:
            st.error("氏名を入力してください。")
        elif new_staff_name in current_staff:
            st.warning(f"「{new_staff_name}」さんは既に登録されています。")
        else:
            # 💡 【本来の美しい設計】名前は名前の列、職種はマルチセレクトの列へそれぞれ個別に保存！
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": STAFF_DB_ID},
                "properties": {
                    "名前": {"title": [{"text": {"content": new_staff_name}}]},
                    "職種": {"multi_select": [{"name": skill} for skill in selected_skills]}
                }
            }
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                st.success(f"🎉 「{new_staff_name}」さんを登録しました！")
                st.rerun()
            else:
                st.error(f"追加に失敗しました。Notion側の『職種』列が【マルチセレクト型】になっているか再度ご確認ください。(エラーコード: {res.status_code})")

with col_s2:
    st.subheader("🗑️ スタッフの削除")
    if current_staff:
        del_target = st.selectbox("削除するスタッフを選択してください", list(current_staff.keys()))
        if st.button("🗑️ このスタッフを削除する", use_container_width=True):
            res = requests.patch(f"https://api.notion.com/v1/pages/{current_staff[del_target]}", headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_target}」さんの登録を削除しました。")
                st.rerun()
    else:
        st.info("現在、登録されているスタッフはいません。")

st.markdown("---")
st.link_button("Notionで直接生データを確認する", f"https://app.notion.com/p/{SHIFT_DB_ID}")
