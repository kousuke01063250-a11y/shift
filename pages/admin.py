import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ページ設定
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
    input_password = st.text_input("パスワードを入力してください", type="password")
    if input_password:
        if input_password == "admin123":
            st.session_state["password_correct"] = True
            st.rerun() 
        else:
            st.error("😕 パスワードが違います。")
    return False

if not check_password():
    st.stop()

# ==========================================
# 🔑 Notion基本設定
# ==========================================
NOTION_TOKEN = "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"
SHIFT_DB_ID = "376f6a7e7de880279373de917797c6ff"
STAFF_DB_ID = "379f6a7e7de880a9ab76e859e099c7e0"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ------------------------------------------
# 👥 1. スタッフマスター情報（戦闘力・職種）の読み込み
# ------------------------------------------
staff_query_url = f"https://api.notion.com/v1/databases/{STAFF_DB_ID}/query"
staff_res = requests.post(staff_query_url, headers=headers)

staff_info_dict = {}  # { "スタッフ名": {"skills": [...], "power": 3} }
current_staff_ids = {}

if staff_res.status_code == 200:
    for page in staff_res.json().get("results", []):
        page_id = page.get("id")
        props = page.get("properties", {})
        try:
            name_text = props["名前"]["title"][0]["text"]["content"].strip()
            current_staff_ids[name_text] = page_id
            
            # 職種（マルチセレクト）の取得
            multi_select = props.get("職種", {}).get("multi_select", [])
            skills = [item["name"] for item in multi_select]
            
            # ✨新設：戦闘力（数値プロパティ）の取得（未設定なら一律1点とする）
            power_val = props.get("戦闘力", {}).get("number")
            if power_val is None:
                power_val = 1
                
            staff_info_dict[name_text] = {
                "skills": skills,
                "power": int(power_val)
            }
        except (KeyError, IndexError):
            continue

# ==========================================
# 📊 2. シフト確認 & 総戦闘力シミュレーター
# ==========================================
st.title("📊 シフト確認 & 総戦闘力シミュレーター")

today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)
week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# 30分刻みの時間軸配列を作成 (09:00 〜 22:00)
time_slots = []
for hour in range(9, 22):
    time_slots.append(f"{hour:02d}:00")
    time_slots.append(f"{hour:02d}:30")
time_slots.append("22:00")

# 最新シフトデータの取得
parsed_records = []
query_url = f"https://api.notion.com/v1/databases/{SHIFT_DB_ID}/query"
response = requests.post(query_url, headers=headers)

if response.status_code == 200:
    for page in response.json().get("results", []):
        props = page.get("properties", {})
        try:
            r_name = props["スタッフ"]["title"][0]["text"]["content"].strip()
            r_start = props["開始"]["rich_text"][0]["text"]["content"]
            r_end = props["終了"]["rich_text"][0]["text"]["content"]
            r_shift = props["シフト"]["rich_text"][0]["text"]["content"]
            
            if r_start != "-" and r_end != "-":
                s_info = staff_info_dict.get(r_name, {"skills": [], "power": 1})
                display_name = f"{r_name} (💪戦闘力:{s_info['power']})"
                
                parsed_records.append({
                    "純粋な名前": r_name,
                    "スタッフ": display_name,
                    "日付": r_start.split(" ")[0],
                    "開始時刻": datetime.strptime(r_start, "%Y-%m-%d %H:%M"),
                    "終了時刻": datetime.strptime(r_end, "%Y-%m-%d %H:%M"),
                    "シフト": r_shift
                })
        except (KeyError, IndexError):
            continue

df_all = pd.DataFrame(parsed_records) if parsed_records else pd.DataFrame()

# 📅 曜日選択
selected_day_index = st.selectbox("確認・シミュレーションする曜日を選択してください", range(7), format_func=lambda x: f"{target_dates[x]} ({week_days[x]}曜日)")
selected_date_str = target_dates[selected_day_index]

# 🎯 総戦闘力の制約（目標値）のUI設定
st.markdown("### 🎯 配置総戦闘力の制約設定 (〇〇以上 〜 〇〇以下)")
col_tgt1, col_tgt2 = st.columns(2)
with col_tgt1:
    min_strength_target = st.number_input("📉 必要最低限の総戦闘力 (これ以上必要)", min_value=0, value=3, step=1)
with col_tgt2:
    max_strength_target = st.number_input("📈 上限の総戦闘力 (これ以下に抑える)", min_value=0, value=8, step=1)

st.markdown("---")

# 🧮 30分ごとの総戦闘力計算ロジック
if not df_all.empty:
    df_filtered = df_all[df_all["日付"] == selected_date_str]
else:
    df_filtered = pd.DataFrame()

timeline_data = []

for ts in time_slots[:-1]:
    current_slot_dt = datetime.strptime(f"{selected_date_str} {ts}", "%Y-%m-%d %H:%M")
    
    total_power_at_slot = 0
    available_staff_names = []
    
    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            if row["開始時刻"] <= current_slot_dt < row["終了時刻"]:
                name = row["純粋な名前"]
                s_info = staff_info_dict.get(name, {"skills": [], "power": 1})
                
                # その時間帯にいるスタッフの戦闘力を加算
                total_power_at_slot += s_info["power"]
                available_staff_names.append(f"{name}({s_info['power']})")

    # 制約を満たしているか判定
    is_safe = min_strength_target <= total_power_at_slot <= max_strength_target
    status_str = "🟢 適正" if is_safe else ("🚨 戦力不足" if total_power_at_slot < min_strength_target else "⚠️ コスト過剰")

    timeline_data.append({
        "時間帯": ts,
        "現在の総戦闘力": total_power_at_slot,
        "下限目標": min_strength_target,
        "上限目標": max_strength_target,
        "判定結果": status_str,
        "出勤可能スタッフ": ", ".join(available_staff_names)
    })

df_sim = pd.DataFrame(timeline_data)

# 🏆 シフト制約の充足スコアを算出
total_slots = len(df_sim)
safe_slots = sum(1 for row in timeline_data if min_strength_target <= row["現在の総戦闘力"] <= max_strength_target)
constraint_score = int((safe_slots / total_slots) * 100) if total_slots > 0 else 0

st.header("🏆 シフト制約の評価スコア")
col_sc1, col_sc2 = st.columns(2)
with col_sc1:
    st.metric(label="✨ 制約充足スコア (時間帯ベース)", value=f"{constraint_score} / 100 点")
with col_sc2:
    st.metric(label="📅 制約を完全に満たしている時間帯", value=f"{safe_slots} / {total_slots} コマ")

# 📊 総戦闘力の推移グラフ
st.markdown("### 📈 時間帯別の総戦闘力推移")
fig_sim = px.line(df_sim, x="時間帯", y=["現在の総戦闘力", "下限目標", "上限目標"], title="時間帯ごとの総戦闘力と制約ライン", line_shape="hv")
st.plotly_chart(fig_sim, use_container_width=True)

# 📋 詳細テーブル
st.subheader("🕵️‍♂️ 30分ごとの詳細シミュレーションデータ")
st.dataframe(df_sim, use_container_width=True)

st.markdown("---")

# ==========================================
# 👥 3. スタッフアカウント管理（追加・削除）
# ==========================================
st.header("👥 スタッフアカウント管理")

col_s1, col_s2 = st.columns(2)
with col_s1:
    st.subheader("➕ スタッフの新規追加")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：高部 光佑", key="s_add_name")
    new_staff_power = st.number_input("このスタッフの戦闘力（点数）を設定してください", min_value=1, value=3, step=1, key="s_add_power")
    
    if st.button("➕ このスタッフを追加する", use_container_width=True, key="s_add_btn"):
        if not new_staff_name:
            st.error("氏名を入力してください。")
        elif new_staff_name in current_staff_ids:
            st.warning(f"「{new_staff_name}」さんは既に登録されています。")
        else:
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": STAFF_DB_ID},
                "properties": {
                    "名前": {"title": [{"text": {"content": new_staff_name}}]},
                    "戦闘力": {"number": new_staff_power}
                }
            }
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                st.success(f"🎉 「{new_staff_name}」さん（戦闘力: {new_staff_power}）を登録しました！")
                st.rerun()
            else:
                st.error("Notionへの追加に失敗しました。スタッフ一覧DBに『戦闘力』という名前の【数値型】プロパティがあるか確認してください。")

with col_s2:
    st.subheader("🗑️ スタッフの削除")
    if current_staff_ids:
        del_target = st.selectbox("削除するスタッフを選択してください", list(current_staff_ids.keys()))
        if st.button("🗑️ このスタッフを削除する", use_container_width=True):
            res = requests.patch(f"https://api.notion.com/v1/pages/{current_staff_ids[del_target]}", headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_target}」さんの登録を削除しました。")
                st.rerun()
