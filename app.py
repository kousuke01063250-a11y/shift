import streamlit as st
from datetime import datetime, timedelta
import requests

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

# ページ設定（スタッフの提出フォーム専用）
st.set_page_config(page_title="シフト提出フォーム", layout="centered")
st.title("📝 シフト希望 提出フォーム")

# ------------------------------------------
# 👥 【最適化】登録スタッフのマスターデータ
# ------------------------------------------
# 💡 メンバーが増減した場合は、ここのリストの文字を書き換えるだけで自動反映されます
STAFF_LIST = [
    "選択してください",  # 初期値のバリデーション用
    "高部 光佑",
    "スタッフA",
    "スタッフB",
    "スタッフC"
]

# ------------------------------------------
# 💡 自動で「来週の月曜日」の日付を計算するロジック
# ------------------------------------------
today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)

week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

st.info(f"現在の提出対象：**{next_monday.strftime('%Y年%m月%d日')}（月）** 〜 **{(next_monday + timedelta(days=6)).strftime('%Y年%m月%d日')}（日）** の1週間分")

# 30分単位の時間枠を作成
time_slots = []
for hour in range(9, 22):
    time_slots.append(f"{hour:02d}:00")
    time_slots.append(f"{hour:02d}:30")
time_slots.append("22:00")

# ------------------------------------------
# シフト提出フォーム本体
# ------------------------------------------
with st.form(key="weekly_shift_form", clear_on_submit=False):
    # 💡 テキスト入力から「セレクトボックス」に変更
    name = st.selectbox("あなたのお名前を選択してください", STAFF_LIST, index=0)
    st.markdown("---")
    
    tabs = st.tabs([f"{d}曜日" for d in week_days])
    weekly_data = {}
    
    for i, day_name in enumerate(week_days):
        date_str = target_dates[i]
        with tabs[i]:
            st.subheader(f"📅 {date_str} ({day_name}) の希望")
            is_off = st.checkbox("この日は出勤できない（終日休み）", key=f"off_{date_str}")
            
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.selectbox("入り時間（開始）", time_slots, index=0, key=f"start_{date_str}", disabled=is_off)
            with col2:
                end_time = st.selectbox("上がり時間（終了）", time_slots, index=1, key=f"end_{date_str}", disabled=is_off)
            
            weekly_data[date_str] = {"day_name": day_name, "is_off": is_off, "start": start_time, "end": end_time}
            
    st.markdown("---")
    submit_button = st.form_submit_button(label="🚀 1週間分のシフトをまとめて提出する")

# ------------------------------------------
# 🚀 送信・重複データ上書きロジック
# ------------------------------------------
if submit_button:
    if name == "選択してください":
        st.error("お名前を正しく選択してください。")
    else:
        # 🔄 同じスタッフの「来週分」の既存データを事前に検索してアーカイブする
        query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
        
        filter_payload = {
            "filter": {
                "property": "スタッフ",
                "title": {
                    "equals": name
                }
            }
        }
        
        search_res = requests.post(query_url, headers=headers, json=filter_payload)
        
        if search_res.status_code == 200:
            existing_pages = search_res.json().get("results", [])
            for page in existing_pages:
                page_id = page.get("id")
                props = page.get("properties", {})
                try:
                    r_start = props["開始"]["rich_text"][0]["text"]["content"]
                    if r_start != "-":
                        record_date = r_start.split(" ")[0]
                        if record_date in target_dates:
                            update_url = f"https://api.notion.com/v1/pages/{page_id}"
                            requests.patch(update_url, headers=headers, json={"archived": True})
                except (KeyError, IndexError):
                    continue

        # ✍️ 最新のシフトデータを新規保存
        success_count = 0
        error_count = 0
        
        for date_str, info in weekly_data.items():
            if info["is_off"]:
                status_text = "終日休み"
                start_dt = "-"
                end_dt = "-"
            else:
                status_text = f"{info['start']} 〜 {info['end']}"
                start_dt = f"{date_str} {info['start']}"
                end_dt = f"{date_str} {info['end']}"
            
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": DATABASE_ID}, 
                "properties": {
                    "スタッフ": {"title": [{"text": {"content": name}}]},
                    "開始": {"rich_text": [{"text": {"content": start_dt}}]},
                    "終了": {"rich_text": [{"text": {"content": end_dt}}]},
                    "シフト": {"rich_text": [{"text": {"content": status_text}}]}
                }
            }
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                success_count += 1
            else:
                error_count += 1
        
        if error_count == 0:
            st.success(f"🎉 送信完了！{name}さんの最新の1週間分のシフト希望に上書き・同期しました。")
        else:
            st.error("送信に失敗しました。管理者にお問い合わせください。")
