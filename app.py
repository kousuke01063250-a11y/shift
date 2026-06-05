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
            st.success(f"🎉 送信完了！{name}さんの1週間分のシフト希望をNotionへ同期しました。")
            st.rerun()
        else:
            st.warning(f"一部送信に失敗しました（成功: {success_count}件, 失敗: {error_count}件）")


# ------------------------------------------
# 2. シフト状況の可視化（管理者用デバッグ強化版）
# ------------------------------------------
st.markdown("---")
st.header("📊 2. シフト確認ダッシュボード（管理者用）")

parsed_records = []
debug_raw_texts = [] # パースに失敗した生の文字を突っ込む箱

query_url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100"
response = requests.get(query_url, headers=headers)

if response.status_code == 200:
    notion_data = response.json()
    blocks = notion_data.get("results", [])
    
    for block in reversed(blocks):
        if block.get("type") == "paragraph":
            text_list = block["paragraph"]["rich_text"]
            if text_list:
                raw_text = text_list[0]["text"]["content"]
                debug_raw_texts.append(raw_text) # デバッグ用に全テキストを記録
                
                # 🚀 【パース強化】より安全に、かつ柔軟に文字列を抽出
                if "スタッフ:" in raw_text and "開始:" in raw_text:
                    try:
                        # 区切り文字 `|` で分解
                        parts = [p.strip() for p in raw_text.split("|")]
                        
                        # それぞれの要素から値を取り出す
                        r_name = [p for p in parts if "スタッフ:" in p][0].split(":")[1].strip()
                        r_date = [p for p in parts if "日付:" in p][0].split(":")[1].split("(")[0].strip()
                        r_shift = [p for p in parts if "シフト:" in p][0].split(":")[1].strip()
                        r_start = [p for p in parts if "開始:" in p][0].split(":")[1].strip()
                        r_end = [p for p in parts if "終了:" in p][0].split(":")[1].strip()
                        
                        if r_start != "-" and r_end != "-":
                            parsed_records.append({
                                "スタッフ": r_name,
                                "日付": r_date,
                                "シフト": r_shift,
                                "開始": r_start,
                                "終了": r_end
                            })
                    except Exception as e:
                        continue

# --- 画面描画ロジック ---
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
        st.info(f"選択された日（{selected_date_str}）に出勤可能なスタッフはいません。※『終日休み』以外の希望があるか確認してください。")

else:
    # 🔍 【超重要】パースに失敗している場合、Notionから何が取れているかを画面に出す
    st.warning("⚠️ Notionからデータは取得できましたが、解析（パース）に失敗しているか、データ形式が一致しません。")
    if debug_raw_texts:
        st.subheader("🛠️ デバッグ情報：Notionから取得した生のテキストデータ")
        st.write("Pythonが読み込んでいる実際の文字は以下です。これらを解析できるようにプログラムを即座にチューニングします：")
        for txt in debug_raw_texts[:5]: # 直近5件を表示
            st.code(txt)
    else:
        st.info("Notionのページ内に、まだテキストブロック（シフトデータ）が見つかりません。")

st.markdown("---")
st.link_button("Notionで直接生データを確認する", f"https://app.notion.com/p/{PAGE_ID}")
