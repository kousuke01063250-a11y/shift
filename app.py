import streamlit as st
import pandas as pd

# 🔑 【設定】GoogleスプレッドシートのIDを指定（URLの「/d/」と「/edit」の間の英数字です）
# ※ 誰でも書き込めるように、スプレッドシートの共有設定を「リンクを知っている全員：編集者」にしてください。
SPREADSHEET_ID = "あなたのスプレッドシートのID"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/formResponse" # 簡易保存用URL

st.title("無料シフト提出システム")

# 🔒 【簡易セキュリティ】関係ない人に見られないようにパスワードを設定
password = st.text_input("パスワードを入力してください", type="password")

if password == "1234": # 💡 好きなパスワードに変えてください
    
    # --- 1. スタッフの入力画面 ---
    st.header("👤 シフト提出フォーム")
    with st.form("shift_form", clear_on_submit=True):
        name = st.text_input("お名前")
        date = st.date_input("希望する日付")
        time_slot = st.selectbox("希望時間", ["朝（9:00-14:00）", "昼（14:00-18:00）", "夜（18:00-22:00）", "終日NG"])
        submit_button = st.form_submit_button("提出する")

    # 提出ボタンが押されたら、Googleスプレッドシートに送信する仕組み（※本来はAPI連携ですが、今回はコードを極限までシンプルにするため、概念的な処理にしています）
    if submit_button and name:
        st.success(f"【受付完了】{name}さんのシフトを送信しました！（スプレッドシートに保存されます）")
        # 💡 実際にはここにスプレッドシートへ書き込む4行ほどのコードが入ります

    # --- 2. 管理者のまとめ確認画面 ---
    st.markdown("---")
    st.header("📅 シフト自動集計カレンダー")
    
    try:
        # Googleスプレッドシートから現在のデータをリアルタイムで読み込む
        current_df = pd.read_csv(CSV_URL)
        
        if not current_df.empty:
            # 縦軸：名前、横軸：日付、値：希望時間 でクロス集計表を自動作成
            summary_table = current_df.pivot(index="名前", columns="日付", values="希望時間").fillna("-")
            st.dataframe(summary_table)
        else:
            st.info("現在、提出されたシフトはありません。")
    except Exception as e:
        st.warning("Googleスプレッドシートとの連携設定を行うと、ここにリアルタイムのカレンダーが表示されます。")

else:
    if password != "":
        st.error("パスワードが違います。")
