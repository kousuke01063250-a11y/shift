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

# ==========================================
# 🔌 ✨【新設】Notion接続ステータス確認システム
# ==========================================
st.sidebar.title("🔌 接続ステータス")

def check_db_connection(db_id, db_name):
    url = f"https://api.notion.com/v1/databases/{db_id}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        st.sidebar.success(f"🟢 {db_name}: 接続正常")
        return True
    else:
        st.sidebar.error(f"🔴 {db_name}: 接続エラー ({res.status_code})")
        return False

shift_ok = check_db_connection(SHIFT_DB_ID, "シフトDB")
staff_ok = check_db_connection(STAFF_DB_ID, "スタッフDB")
pos_ok = check_db_connection(POSITION_DB_ID, "ポジションDB")

if not pos_ok:
    st.sidebar.warning("⚠️ ポジションDBの右上の『•••』からコネクト（接続）が追加されているかご確認ください。")


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
            # 💡 安全対策：空のページや名前未入力のページはスキップする
            title_obj = page["properties"]["ポジション名"]["title"]
            if title_obj:
                pos_text = title_obj[0]["text"]["content"].strip()
                if pos_text: # 文字が空でない場合のみ追加
                    current_positions[pos_text] = page_id
        except (KeyError, IndexError):
            continue

# 現在登録されているポジションを横並びのバッジで視覚化
if current_positions:
    st.markdown("**現在登録されているポジション一覧:**")
    cols = st.columns(len(current_positions) if len(current_positions) < 10 else 10)
    for idx, pos_name in enumerate(current_positions.keys()):
        cols[idx % len(cols)].info(f"● {pos_name}")
else:
    st.warning("⚠️ 現在、有効なポジションが登録されていません。下のフォームから追加してください。")

col_p1, col_p2 = st.columns(2)
with col_p1:
    new_pos_name = st.text_input("🎨 新しいポジション名を入力", placeholder="例：ホール、焼き場、仕込み")
    if st.button("➕ ポジションを新規追加する", use_container_width=True):
        if new_pos_name:
            new_pos_name = new_pos_name.strip()
            if new_pos_name in current_positions:
                st.warning("そのポジションは既に存在します。")
            else:
                res = requests.post("https://api.notion.com/v1/pages", headers=headers, json={
                    "parent": {"database_id": POSITION_DB_ID},
                    "properties": {"ポジション名": {"title": [{"text": {"content": new_pos_name}}]}}
                })
                if res.status_code == 200:
                    st.success(f"🎉 ポジション「{new_pos_name}」を追加しました！")
                    st.rerun()
        else:
            st.error("ポジション名を入力してください。")

with col_p2:
    if current_positions:
        del_pos_target = st.selectbox("🗑️ 削除するポジションを選択", list(current_positions.keys()))
        if st.button("🗑️ 選択したポジションを削除", use_container_width=True):
            res = requests.patch(f"https://api.notion.com/v1/pages/{current_positions[del_pos_target]}", headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_pos_target}」を削除しました。")
                st.rerun()

st.markdown("---")

# ==========================================
# 👥 スタッフアカウント管理
# ==========================================
st.header("👥 スタッフアカウント管理")

staff_query_url = f"https://api.notion.com/v1/databases/{STAFF_DB_ID}/query"
staff_res = requests.post(staff_query_url, headers=headers)
current_staff = {}
if staff_res.status_code == 200:
    for page in staff_res.json().get("results", []):
        page_id = page.get("id")
        try:
            name_text = page["properties"]["名前"]["title"][0]["text"]["content"]
            current_staff[name_text] = page_id
        except (KeyError, IndexError):
            continue

col_s1, col_s2 = st.columns(2)
with col_s1:
    st.subheader("➕ スタッフの新規追加")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：高部 光佑", key="s_add_name")
    
    # 💡 上で動的に取得した current_positions のキーを100%確実にリストとして展開
    position_options = list(current_positions.keys())
    selected_skills = st.multiselect("担当できるポジションをすべて選択してください（複数可）", options=position_options)
    
    if st.button("➕ このスタッフを追加する", use_container_width=True, key="s_add_btn"):
        if not new_staff_name:
            st.error("氏名を入力してください。")
        elif new_staff_name in current_staff:
            st.warning(f"「{new_staff_name}」さんは既に登録されています。")
        else:
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
                st.error(f"追加に失敗しました。(エラーコード: {res.status_code})")

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
