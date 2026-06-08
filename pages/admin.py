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

# パスワードが通らなければ、これ以降のコード（Notion通信やグラフ描画）は絶対に実行しない
if not check_password():
    st.stop()

# ==========================================
# 🔑 Notion基本設定（ここからは認証が通った場合のみ実行されます）
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de880279373de917797c6ff"  

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.title("📊 シフト確認ダッシュボード（管理者用）")

# （以下、カレンダー・グラフ描画コードが続く...）
