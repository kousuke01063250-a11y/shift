import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# ==========================================
# 🔑 Notion基本設定
# ==========================================
NOTION_TOKEN = "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"
PAGE_ID = "376f6a7e7de880a98d1fd3e6431a03b6"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.set_page_config(page_title="1週間シフト管理システム", layout="wide")
st.title("📅 1週間一括・30分単位 シフト提出システム")

# ------------------------------------------
# 💡 自動で「来週の月曜日」の日付を計算するロジック
# ------------------------------------------
today = datetime.today()
# 次の月曜日までの日数を計算（今日が月曜なら7日後、火曜なら6日後...）
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)

# ------------------------------------------
# 1. シフト提出フォーム（1週間分一括）
# ------------------------------------------
st.header("1. シフト希望の入力（スタッフ用）")
st.info(f"現在の提出対象：**{next_monday.strftime('%Y年%m月%d日')}（月）** 〜 **{(next_monday + timedelta(days=6)).strftime('%Y年%m月%d日')}（日）** の1週間分")

# 30分刻みの時間リストを生成 (09:00 〜 22:00)
time_slots = []
for hour in range(9, 22):
    time_slots.append(f"{hour:02d}:00")
    time_slots.append(f"{hour:02d}:30")
time_slots.append("22:00")

with st.form(key="weekly_shift_form", clear_on_submit=False):
    # お名前入力
    name = st.text_input("お名前（フルネーム）", placeholder="例：高部 光佑")
    st.markdown("---")
    
    # 曜日ごとの入力スペースを横並び（タブ）で綺麗に配置
    week_days = ["月", "火", "水", "木", "金", "土", "日"]
    tabs = st.tabs([f"{d}曜日" for d in week_days])
    
    # 曜日ごとの入力データを保持する辞書
    weekly_data = {}
    
    for i, day_name in enumerate(week_days):
        target_date = next_monday + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        
        with tabs[i]:
            st.subheader(f"📅 {date_str} ({day_name}) の希望")
            
            # 「この日は入れない（休み）」のチェックボックス
            is_off = st.checkbox("この日は出勤できない（終日休み）", key=f"off_{date_str}")
            
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.selectbox("入り時間（開始）", time_slots, index=0, key=f"start_{date_str}", disabled=is_off)
            with col2:
                # 終了時間はデフォルトで一コマ後ろ（09:30）にしておく
                end_time = st.selectbox("上がり時間（終了）", time_slots, index=1, key=f"end_{date_str}", disabled=is_off)
            
            # データを記憶
            weekly_data[date_str] = {
                "day_name": day_name,
                "is_off": is_off,
                "start": start_time,
                "end": end_time
            }
            
    st.markdown("---")
    submit_button = st.form_submit_button(label="🚀 1週間分のシフトをまとめて提出する")

# 送信ボタンが押された時の処理
if submit_button:
    if not name:
        st.error("お名前を入力してください。")
    else:
        success_count = 0
        error_count = 0
        
        # 7日分のデータをループしてNotionに1つずつ送信
        for date_str, info in weekly_data.items():
            # 休みの日も「休み」というレコードとしてNotionに送る（最適化で計算しやすくするため）
            if info["is_off"]:
                status_text = "終日休み"
                start_dt = "-"
                end_dt = "-"
            else:
                status_text = f"{info['start']} 〜 {info['end']}"
                start_dt = f"{date_str} {info['start']}"
                end_dt = f"{date_str} {info['end']}"
            
            # Notionへの送信ペイロード
            create_url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"page_id": PAGE_ID},
                "properties": {
                    "title": {
                        "title": [{"text": {"content": f"【シフト】{name}"}}]
                    }
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": f"スタッフ:{name} | 日付:{date_str}({info['day_name']}) | シフト:{status_text} | 開始:{start_dt} | 終了:{end_dt}"}}]
                        }
                    }
                ]
            }
            
            res = requests.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                success_count += 1
            else:
                error_count += 1
        
        if error_count == 0:
            st.success(f"🎉 送信完了！{name}さんの1週間分（7日程）のシフト希望をすべてNotionへ同期しました。")
        else:
            st.warning(f"一部送信に失敗しました（成功: {success_count}件, 失敗: {error_count}件）")

# ------------------------------------------
# 2. 提出されたデータの確認画面（簡易版）
# ------------------------------------------
st.markdown("---")
st.header("📊 提出データ確認（簡易ビュー）")

base_data = []
query_url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
response = requests.get(query_url, headers=headers)

if response.status_code == 200:
    notion_data = response.json()
    for block in notion_data.get("results", []):
        if block.get("type") == "child_page":
            p_title = block["child_page"]["title"]
            if "【シフト】" in p_title:
                p_name = p_title.replace("【シフト】", "")
                base_data.append(dict(スタッフ=p_name, ステータス="提出完了"))

if base_data:
    df = pd.DataFrame(base_data).drop_duplicates()
    st.dataframe(df, use_container_width=True)
else:
    st.info("まだ今週の提出データはありません。")

st.link_button("Notionで直接確認する", f"https://app.notion.com/p/{PAGE_ID}")
