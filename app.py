import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import json

# ==========================================
# 🔑 Notion基本設定
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de8805b850c000ccfc4e205"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.set_page_config(page_title="シフト管理システム（デバッグモード）", layout="wide")
st.title("🛠️ 原因究明デバッグ画面")

today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0:
    days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)

week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# ------------------------------------------
# フォーム
# ------------------------------------------
with st.form(key="debug_form"):
    name = st.text_input("テスト用お名前", value="テストユーザー")
    submit_button = st.form_submit_button(label="🔍 テスト送信してエラー原因を暴く")

if submit_button:
    # 1日分だけテスト送信してみる
    date_str = target_dates[0]
    create_url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": DATABASE_ID}, 
        "properties": {
            "スタッフ": {"title": [{"text": {"content": name}}]},
            "開始": {"rich_text": [{"text": {"content": f"{date_str} 09:00"}}]},
            "終了": {"rich_text": [{"text": {"content": f"{date_str} 18:00"}}]},
            "シフト": {"rich_text": [{"text": {"content": "09:00 〜 18:00"}}]}
        }
    }
    
    res = requests.post(create_url, headers=headers, json=payload)
    
    st.markdown("---")
    st.subheader("📡 Notionサーバーからの生の返答（レスポンス）")
    
    st.write(f"**ステータスコード:** `{res.status_code}`")
    
    try:
        error_details = res.json()
        st.error(f"**エラーコード:** `{error_details.get('code')}`")
        st.error(f"**詳細メッセージ:** `{error_details.get('message')}`")
        
        st.markdown("**送信したデータ構造（ペイロード）の確認:**")
        st.json(payload)
        st.markdown("**Notionから返ってきた生のJSON:**")
        st.json(error_details)
        
    except Exception as e:
        st.write("JSONの解析に失敗しました。生のテキスト:")
        st.code(res.text)

# ------------------------------------------
# 読み込みテスト
# ------------------------------------------
st.markdown("---")
st.subheader("📥 データベース読み込みテスト")
query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
res_query = requests.post(query_url, headers=headers)
st.write(f"**読み込みステータスコード:** `{res_query.status_code}`")
if res_query.status_code != 200:
    try:
        st.json(res_query.json())
    except:
        st.code(res_query.text)
