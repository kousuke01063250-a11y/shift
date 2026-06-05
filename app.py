import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests

# ==========================================
# 🔑 Notion基本設定（高部さんの情報に固定）
# ==========================================
NOTION_TOKEN = "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"
DATABASE_ID = "376f6a7e7de880a98d1fd3e6431a03b6"

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
        
        # 🚀 【修正】実際にNotion APIへシフトデータを送信して保存するロジック
        create_url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "スタッフ": {"title": [{"text": {"content": name}}]},
                "開始": {"rich_text": [{"text": {"content": start_dt}}]},
                "終了": {"rich_text": [{"text": {"content": end_dt}}]},
                "シフト": {"rich_text": [{"text": {"content": shift_type}}]}
            }
        }
        res = requests.post(create_url, headers=headers, json=payload)
        
        if res.status_code == 200:
            st.success(f"【送信完了】 {name}さん: Notionのデータベースへダイレクトに反映されました！")
        else:
            st.error(f"Notionへの送信に失敗しました。ステータスコード: {res.status_code}")
    else:
        st.error("お名前を入力してください。")

# ------------------------------------------
# 2. シフト状況の確認と可視化（管理者用）
# ------------------------------------------
st.markdown("---")
st.header("📊 シフト状況の確認（管理者用）")

# 🚀 【修正】古いスプレッドシートからの読み込みを廃止し、Notionからリアルタイム同期
base_data = []
query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
response = requests.post(query_url, headers=headers)

if response.status_code == 200:
    notion_data = response.json()
    for page in notion_data.get("results", []):
        props = page.get("properties", {})
        try:
            p_name = props["スタッフ"]["title"][0]["text"]["content"]
            p_start = props["開始"]["rich_text"][0]["text"]["content"]
            p_end = props["終了"]["rich_text"][0]["text"]["content"]
            p_shift = props["シフト"]["rich_text"][0]["text"]["content"]
            base_data.append(dict(スタッフ=p_name, 開始=p_start, 終了=p_end, シフト=p_shift))
        except KeyError:
            # プロパティ名が一致しない、または空の列がある場合はスキップ
            continue

# 万が一Notionが空だった場合のサンプル
if not base_data:
    base_data = [
        dict(スタッフ="初期サンプル", 開始=f"{datetime.today().date()} 09:00", 終了=f"{datetime.today().date()} 14:00", シフト="朝番 (9:00-14:00)")
    ]

df = pd.DataFrame(base_data)

# 🕒 タイムライン図の描画
try:
    fig = px.timeline(
        df, 
        x_start="開始", 
        x_end="終了", 
        y="スタッフ", 
        color="シフト",
        title="本日のタイムライン（Notion同期データ）"
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.info("タイムラインを表示するためのデータを読み込んでいます...")

# 📋 一覧表の表示
st.subheader("提出データ一覧")
st.dataframe(df, use_container_width=True)

# 🔗 Notionへの直接リンク
st.markdown("---")
st.subheader(" 📂 データベースNotion")
st.markdown("すべてのデータは、以下の安全なクラウド上のNotionデータベースに蓄積されています。")
st.link_button("Notionのシフト表を開く", "https://app.notion.com/p/376f6a7e7de880a98d1fd3e6431a03b6")


# ------------------------------------------
# 3. 新規スタッフ登録（管理者用）
# ------------------------------------------
st.markdown("---")
st.header("👥 管理者用：新規スタッフ登録")

with st.form(key="admin_staff_form", clear_on_submit=True):
    new_staff_name = st.text_input("登録するスタッフの氏名")
    max_days_per_week = st.number_input("週の最大出勤可能日数（制約条件）", min_value=1, max_value=7, value=3)
    
    admin_submit = st.form_submit_button(label="スタッフをマスターに登録")

if admin_submit:
    if new_staff_name:
        # 🚀 【修正】スタッフ情報も独立させず、現段階では同じNotionデータベースへ
        # 「スタッフ登録フラグ」のような形で蓄積するか、同じテーブルの別形式として安全に送信します
        staff_payload = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "スタッフ": {"title": [{"text": {"content": f"【マスター】{new_staff_name}"}}]},
                "開始": {"rich_text": [{"text": {"content": f"週上限: {max_days_per_week}日"}}]},
                "終了": {"rich_text": [{"text": {"content": "-"}}]},
                "シフト": {"rich_text": [{"text": {"content": "マスター登録"}}]}
            }
        }
        res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=staff_payload)
        if res.status_code == 200:
            st.success(f"【登録完了】{new_staff_name}さん（週上限 {max_days_per_week}日）をNotionへ登録しました！")
            st.rerun() # 画面を更新して即座に下の表に反映
        else:
            st.error(f"スタッフ登録に失敗しました。ステータスコード: {res.status_code}")
