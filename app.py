import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ==========================================
# 🔑 Notion基本設定（最新の正確なIDに修正）
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de8805b850c000ccfc4e205"  # 👈 コピーしていただいた本物のDB ID

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.set_page_config(page_title="1週間シフト管理システム", layout="wide")
st.title("📅 1週間一括・30分単位 シフト管理システム")

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

# ------------------------------------------
# 1. シフト提出フォーム（スタッフ用）
# ------------------------------------------
st.header("1. シフト希望の入力（スタッフ用）")
st.info(f"現在の提出対象：**{next_monday.strftime('%Y年%m月%d日')}（月）** 〜 **{(next_monday + timedelta(days=6)).strftime('%Y年%m月%d日')}（日）** の1週間分")

time_slots = []
for hour in range(9, 22):
    time_slots.append(f"{hour:02d}:00")
    time_slots.append(f"{hour:02d}:30")
time_slots.append("22:00")

with st.form(key="weekly_shift_form", clear_on_submit=False):
    name = st.text_input("お名前（フルネーム）", placeholder="例：高部 光佑")
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

if submit_button:
    if not name:
        st.error("お名前を入力してください。")
    else:
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
            
            # 正確な宛先に対して、Notionが求める正確なJSONデータ形式で送信
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": DATABASE_ID}, 
                "properties": {
                    "スタッフ": {
                        "title": [
                            {"text": {"content": name}}
                        ]
                    },
                    "開始": {
                        "rich_text": [
                            {"text": {"content": start_dt}}
                        ]
                    },
                    "終了": {
                        "rich_text": [
                            {"text": {"content": end_dt}}
                        ]
                    },
                    "シフト": {
                        "rich_text": [
                            {"text": {"content": status_text}}
                        ]
                    }
                }
            }
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                success_count += 1
            else:
                error_count += 1
        
        if error_count == 0:
            st.success(f"🎉 送信完了！{name}さんの1週間分のシフト希望をデータベースへ直接格納しました。")
            st.rerun()
        else:
            st.error(f"送信に失敗しました（成功: {success_count}件, 失敗: {error_count}件）。Notion側の列の名前（スタッフ、開始、終了、シフト）をもう一度ご確認ください。")


# ------------------------------------------
# 2. シフト状況の可視化
# ------------------------------------------
st.markdown("---")
st.header("📊 2. シフト確認ダッシュボード（管理者用）")

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
    st.info("Notionのデータベース内に、まだ有効なシフトデータが見つかりません。上のフォームから送信してみてください。")

st.markdown("---")
st.link_button("Notionで直接生データを確認する", f"https://app.notion.com/p/{DATABASE_ID}")
