import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests

# ==========================================
# 🔑 Notion基本設定（高部さんの情報に固定）
# ==========================================
NOTION_TOKEN = "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"
PAGE_ID = "376f6a7e7de880a98d1fd3e6431a03b6"  # 👈 page_id として扱います

# API通信用の共通ヘッダー
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.set_page_config(page_title="クラウドシフト管理システム", layout="wide")
st.title(" リアルタイム・シフト管理システム（Notion完全連動版）")

# ------------------------------------------
# 1. シフト提出フォーム（スタッフ用）
# ------------------------------------------
st.header("1. シフト提出（スタッフ用）")
with st.form(key="shift_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("お名前（フルネーム）")
    with col2:
        date = st.date_input("出勤希望日", value=datetime.today())
    with col3:
        shift_type = st.selectbox("シフト帯", ["朝番 (9:00-14:00)", "昼番 (13:00-18:00)", "夜番 (17:00-22:00)", "フル (9:00-22:00)"])
    
    submit_button = st.form_submit_button(label="シフトを提出する")

if submit_button:
    if name:
        time_map = {
            "朝番 (9:00-14:00)": ("09:00", "14:00"),
            "昼番 (13:00-18:00)": ("13:00", "18:00"),
            "夜番 (17:00-22:00)": ("17:00", "22:00"),
            "フル (9:00-22:00)": ("09:00", "22:00")
        }
        start_t, end_t = time_map[shift_type]
        start_dt = f"{date} {start_t}"
        end_dt = f"{date} {end_t}"
        
        # 🚀 【ここを修正】database_id ではなく page_id の配下に「子ページ」として送信します
        create_url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"page_id": PAGE_ID},  # 👈 page_id に変更
            "properties": {
                "title": {  # 👈 ページとして送るため、一番親のタイトルを設定
                    "title": [{"text": {"content": f"{name}さんのシフト"}}]
                }
            },
            # ページの中にテキストとしてシフト内容を書き込む
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": f"【スタッフ】{name} | 【日程】{date} | 【シフト】{shift_type}"}}]
                    }
                }
            ]
        }
        res = requests.post(create_url, headers=headers, json=payload)
        
        if res.status_code == 200:
            st.success(f"【送信完了】 {name}さん: Notionのページへ正常に反映されました！")
        else:
            st.error(f"Notionへの送信に失敗しました。ステータスコード: {res.status_code}")
    else:
        st.error("お名前を入力してください。")

# ------------------------------------------
# 2. シフト状況の確認と可視化（管理者用）
# ------------------------------------------
st.markdown("---")
st.header("📊 シフト状況の確認（管理者用）")

base_data = []

# 🚀 ページの子ブロック（送信されたシフト）を読み込むロジック
query_url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
response = requests.get(query_url, headers=headers)

if response.status_code == 200:
    notion_data = response.json()
    for block in notion_data.get("results", []):
        if block.get("type") == "child_page":
            p_title = block["child_page"]["title"]
            if "さんのシフト" in p_title:
                p_name = p_title.replace("さんのシフト", "")
                base_data.append(dict(スタッフ=p_name, 開始=f"{datetime.today().date()} 09:00", 終了=f"{datetime.today().date()} 18:00", シフト="提出あり"))

if not base_data:
    base_data = [
        dict(スタッフ="初期サンプル", 開始=f"{datetime.today().date()} 09:00", 終了=f"{datetime.today().date()} 14:00", シフト="朝番 (9:00-14:00)")
    ]

df = pd.DataFrame(base_data)

# 📋 一覧表の表示
st.subheader("提出データ一覧")
st.dataframe(df, use_container_width=True)

# 🔗 Notionへの直接リンク
st.markdown("---")
st.subheader(" 📂 データベースNotion")
st.markdown("すべてのデータは、以下の安全なクラウド上のNotionページに蓄積されます。")
st.link_button("Notionのシフト表を開く", "https://app.notion.com/p/376f6a7e7de880a98d1fd3e6431a03b6")
