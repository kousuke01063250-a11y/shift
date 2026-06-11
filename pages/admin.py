import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

# 最最適化ライブラリのインポートチェック
try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False

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
# 👥 1. スタッフマスター情報の読み込み
# ------------------------------------------
staff_query_url = f"https://api.notion.com/v1/databases/{STAFF_DB_ID}/query"
staff_res = requests.post(staff_query_url, headers=headers)

staff_info_dict = {}  
current_staff_ids = {}
all_positions_set = set() # 存在する全ポジションを自動抽出

if staff_res.status_code == 200:
    for page in staff_res.json().get("results", []):
        page_id = page.get("id")
        props = page.get("properties", {})
        try:
            name_text = props["名前"]["title"][0]["text"]["content"].strip()
            current_staff_ids[name_text] = page_id
            
            multi_select = props.get("職種", {}).get("multi_select", [])
            skills = [item["name"] for item in multi_select]
            for sk in skills:
                all_positions_set.add(sk)
            
            power_val = props.get("戦闘力", {}).get("number")
            if power_val is None: power_val = 1
                
            staff_info_dict[name_text] = {
                "skills": skills,
                "power": int(power_val)
            }
        except (KeyError, IndexError):
            continue

all_positions = sorted(list(all_positions_set))

# ==========================================
# 📊 2. データ構造の定義
# ==========================================
today = datetime.today()
days_until_next_monday = (0 - today.weekday()) % 7
if days_until_next_monday == 0: days_until_next_monday = 7
next_monday = today + timedelta(days=days_until_next_monday)
week_days = ["月", "火", "水", "木", "金", "土", "日"]
target_dates = [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

time_slots = []
for hour in range(9, 22):
    time_slots.append(f"{hour:02d}:00")
    time_slots.append(f"{hour:02d}:30")
time_slots.append("22:00")
slots_without_last = time_slots[:-1]

# 最新希望シフトデータの取得
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
                display_name = f"{r_name} (💪:{s_info['power']})"
                
                parsed_records.append({
                    "純粋な名前": r_name,
                    "スタッフ": display_name,
                    "日付": r_start.split(" ")[0],
                    "開始": r_start,  
                    "終了": r_end,    
                    "開始時刻": datetime.strptime(r_start, "%Y-%m-%d %H:%M"), 
                    "終了時刻": datetime.strptime(r_end, "%Y-%m-%d %H:%M"), 
                    "シフト": r_shift
                })
        except (KeyError, IndexError):
            continue

df_all = pd.DataFrame(parsed_records) if parsed_records else pd.DataFrame()

# 📅 画面UI
st.title("🤖 🚀 数理最適化シフト自動生成システム")
selected_day_index = st.selectbox("シフトを自動生成する曜日を選択してください", range(7), format_func=lambda x: f"{target_dates[x]} ({week_days[x]}曜日)")
selected_date_str = target_dates[selected_day_index]

# 🎯 条件設定
st.markdown("### 🎯 1. 現場の総戦闘力制約（目標値）")
col_tgt1, col_tgt2 = st.columns(2)
with col_tgt1:
    min_strength_target = st.number_input("📉 必要な最低総戦闘力", min_value=0, value=3, step=1)
with col_tgt2:
    max_strength_target = st.number_input("📈 上限の総戦闘力 (人件費コスト抑制ライン)", min_value=0, value=8, step=1)

# ポジションごとの最低必要人数の動的UI
st.markdown("### 🛠️ 2. ポジションごとの最低必要人数設定")
position_requirements = {}
if all_positions:
    cols = st.columns(len(all_positions))
    for idx, pos in enumerate(all_positions):
        with cols[idx]:
            position_requirements[pos] = st.number_input(f"👥 {pos}の最低必要人数", min_value=0, value=1, step=1)
else:
    st.info("※Notionのスタッフデータベースに職種（マルチセレクト）がまだ1件も登録されていません。最下部からスタッフを追加してください。")

if not df_all.empty:
    df_filtered = df_all[df_all["日付"] == selected_date_str]
else:
    df_filtered = pd.DataFrame()

st.markdown("---")

# ==========================================
# 🧠 3. 数理最適化（MIP）エンジン
# ==========================================
st.header("🤖 最適化シフト生成エンジン")

if not PULP_AVAILABLE:
    st.error("📦 最適化ライブラリ `PuLP` がインストールされていません。")
else:
    if st.button("🚀 この条件でポジション割当を最適化する (ソルバー起動)", use_container_width=True):
        if df_filtered.empty:
            st.warning("⚠️ 選択された日の希望シフトデータがありません。")
        else:
            with st.spinner("数理最適化ソルバーがポジション重複を排除して計算中..."):
                staff_list = list(staff_info_dict.keys())
                
                # 出勤可能マトリクス
                A = {i: {t: 0 for t in slots_without_last} for i in staff_list}
                for _, row in df_filtered.iterrows():
                    name = row["純粋な名前"]
                    for t in slots_without_last:
                        slot_dt = datetime.strptime(f"{selected_date_str} {t}", "%Y-%m-%d %H:%M")
                        if row["開始時刻"] <= slot_dt < row["終了時刻"]:
                            if name in A: A[name][t] = 1

                # 問題定義
                prob = pulp.LpProblem("Shift_Position_Optimization", pulp.LpMinimize)
                
                # 決定変数
                x = pulp.LpVariable.dicts("assign", ((i, t) for i in staff_list for t in slots_without_last), cat='Binary')
                y = pulp.LpVariable.dicts("pos_assign", ((i, p, t) for i in staff_list for p in all_positions for t in slots_without_last), cat='Binary')
                
                # スラック変数
                slack_under = pulp.LpVariable.dicts("slack_under", slots_without_last, lowBound=0, cat='Continuous')
                slack_over = pulp.LpVariable.dicts("slack_over", slots_without_last, lowBound=0, cat='Continuous')
                slack_pos = pulp.LpVariable.dicts("slack_pos", ((p, t) for p in all_positions for t in slots_without_last), lowBound=0, cat='Continuous')

                # 目的関数（ポジション不足へのペナルティ）
                prob += (
                    pulp.lpSum(slack_under[t] * 1000 + slack_over[t] * 10 for t in slots_without_last) +
                    pulp.lpSum(slack_pos[p, t] * 500 for p in all_positions for t in slots_without_last) +
                    pulp.lpSum(x[i, t] * 1 for i in staff_list for t in slots_without_last)
                )

                # 制約条件
                for t in slots_without_last:
                    # 1. 総戦闘力の上下限制約
                    total_power = pulp.lpSum(staff_info_dict[i]["power"] * x[i, t] for i in staff_list)
                    prob += total_power >= min_strength_target - slack_under[t]
                    prob += total_power <= max_strength_target + slack_over[t]
                    
                    # 2. ポジション別の必要人数制約
                    for p in all_positions:
                        prob += pulp.lpSum(y[i, p, t] for i in staff_list) >= position_requirements[p] - slack_pos[p, t]

                    for i in staff_list:
                        # 3. 希望枠以外の出勤禁止
                        prob += x[i, t] <= A[i][t]
                        
                        # 4. 1人1ポジションの掛け持ち禁止（出勤フラグとの完全連動）
                        prob += pulp.lpSum(y[i, p, t] for p in all_positions) == x[i, t]
                        
                        # 5. スキルを保有していないポジションへの配置禁止
                        for p in all_positions:
                            if p not in staff_info_dict[i]["skills"]:
                                prob += y[i, p, t] == 0

                # ソルバー実行
                prob.solve(pulp.PULP_CBC_CMD(msg=False))
                
                # 結果のデコード
                opt_records = []
                for i in staff_list:
                    current_pos = None
                    start_t = None
                    for idx, t in enumerate(slots_without_last):
                        assigned_pos = None
                        for p in all_positions:
                            if pulp.value(y[i, p, t]) == 1:
                                assigned_pos = p
                                break
                        
                        if assigned_pos != current_pos:
                            if current_pos is not None:
                                opt_records.append({
                                    "スタッフ": i, "ポジション": current_pos,
                                    "表示名": f"{i} (💪:{staff_info_dict[i]['power']})",
                                    "開始": f"{selected_date_str} {start_t}", "終了": f"{selected_date_str} {t}"
                                })
                            start_t = t
                            current_pos = assigned_pos
                            
                    if current_pos is not None:
                        opt_records.append({
                            "スタッフ": i, "ポジション": current_pos,
                            "表示名": f"{i} (💪:{staff_info_dict[i]['power']})",
                            "開始": f"{selected_date_str} {start_t}", "終了": f"{selected_date_str} 22:00"
                        })
                
                st.session_state["opt_df"] = pd.DataFrame(opt_records) if opt_records else pd.DataFrame()
                
                # タイムラインシミュレーションデータの生成
                opt_sim_data = []
                for t in slots_without_last:
                    t_power = sum(staff_info_dict[i]["power"] for i in staff_list if pulp.value(x[i, t]) == 1)
                    is_safe = min_strength_target <= t_power <= max_strength_target
                    status_str = "🟢 適正" if is_safe else ("🚨 戦力不足" if t_power < min_strength_target else "⚠️ コスト過剰")
                    opt_sim_data.append({
                        "時間帯": t, "現在の総戦闘力": t_power, "下限目標": min_strength_target, "上限目標": max_strength_target, "判定結果": status_str
                    })
                st.session_state["opt_sim"] = pd.DataFrame(opt_sim_data)
                st.success("🎉 ポジション掛け持ちを完全に排除した最適化シフトの生成が完了しました！")

# ==========================================
# 📈 4. 最適化結果のダッシュボード表示
# ==========================================
if st.session_state.get("opt_df") is not None and st.session_state.get("opt_sim") is not None:
    df_opt = st.session_state["opt_df"]
    df_opt_sim = st.session_state["opt_sim"]
    
    t_slots = len(df_opt_sim)
    s_slots = sum(1 for _, r in df_opt_sim.iterrows() if r["下限目標"] <= r["現在の総戦闘力"] <= r["上限目標"])
    score = int((s_slots / t_slots) * 100) if t_slots > 0 else 0
    
    st.markdown("---")
    st.subheader("🏆 生成された最適化シフトの評価")
    
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.metric(label="✨ 自動生成シフトの制約充足スコア", value=f"{score} / 100 点")
    with col_res2:
        st.metric(label="📅 目標戦闘力を満たしている時間帯", value=f"{s_slots} / {t_slots} コマ")
        
    st.markdown("### 📈 最適化後の総戦闘力タイムライン推移")
    fig_opt_line = px.line(df_opt_sim, x="時間帯", y=["現在の総戦闘力", "下限目標", "上限目標"], title="最適化アサイン後の総戦闘力推移", line_shape="hv")
    st.plotly_chart(fig_opt_line, use_container_width=True)
    
    st.markdown("### 📅 確定自動生成シフト（ポジション別色分けガントチャート）")
    if not df_opt.empty:
        fig_opt_gantt = px.timeline(df_opt, x_start="開始", x_end="終了", y="表示名", color="ポジション", text="ポジション", title="時間帯別の担当ポジション可視化")
        fig_opt_gantt.update_yaxes(autorange="reversed")
        fig_opt_gantt.update_layout(xaxis=dict(title="時間帯", tickformat="%H:%M"))
        st.plotly_chart(fig_opt_gantt, use_container_width=True)
        st.dataframe(df_opt[["スタッフ", "ポジション", "開始", "終了"]], use_container_width=True)
    else:
        st.info("この条件を満たすためにアサインされたスタッフはいません。")

st.markdown("---")
st.subheader("📋 （参考）スタッフから提出された生の希望シフト")
if not df_filtered.empty:
    fig_raw = px.timeline(df_filtered, x_start="開始", x_end="終了", y="スタッフ", color="スタッフ", text="スタッフ", title="提出された希望シフトの重ね合わせ（Before）")
    fig_raw.update_yaxes(autorange="reversed")
    fig_raw.update_layout(xaxis=dict(title="時間帯", tickformat="%H:%M"))
    st.plotly_chart(fig_raw, use_container_width=True)
else:
    st.info("希望シフトデータがありません。")

# ==========================================
# 👥 5. 【復活＆強化】スタッフアカウント管理
# ==========================================
st.markdown("---")
st.header("👥 スタッフアカウント管理")
col_s1, col_s2 = st.columns(2)

with col_s1:
    st.subheader("➕ スタッフの新規追加")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：山田 太郎", key="s_add_name")
    new_staff_power = st.number_input("このスタッフの戦闘力（点数）を設定してください", min_value=1, value=3, step=1, key="s_add_power")
    
    # ✨ パワーアップ：既存のポジション、あるいはデフォルトの役割から複数選べるように拡張！
    position_options = all_positions if all_positions else ["レジ", "キッチン", "ホール"]
    new_staff_skills = st.multiselect("このスタッフが担当できるポジション（職種）をすべて選択してください", options=position_options, key="s_add_skills")
    
    if st.button("➕ このスタッフをNotionに登録する", use_container_width=True, key="s_add_btn"):
        if not new_staff_name:
            st.error("⚠️ スタッフの名前を入力してください。")
        elif new_staff_name in current_staff_ids:
            st.warning(f"⚠️ 「{new_staff_name}」さんは既に登録されています。")
        else:
            payload = {
                "parent": {"database_id": STAFF_DB_ID},
                "properties": {
                    "名前": {"title": [{"text": {"content": new_staff_name}}]},
                    "戦闘力": {"number": new_staff_power},
                    "職種": {"multi_select": [{"name": p} for p in new_staff_skills]}
                }
            }
            res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
            if res.status_code == 200:
                st.success(f"🎉 「{new_staff_name}」さん（職種: {', '.join(new_staff_skills)}）を新しく登録しました！")
                st.rerun()
            else:
                st.error(f"Notionへの登録に失敗しました。APIエラー: {res.text}")

with col_s2:
    st.subheader("🗑️ スタッフの削除（アーカイブ）")
    if current_staff_ids:
        del_target = st.selectbox("削除するスタッフを選択してください", list(current_staff_ids.keys()))
        st.warning(f"⚠️ 「{del_target}」さんを削除すると、次回からシフト最適化の計算対象外になります。")
        if st.button("🗑️ このスタッフの登録を削除する", use_container_width=True, key="s_del_btn"):
            page_id = current_staff_ids[del_target]
            res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={"archived": True})
            if res.status_code == 200:
                st.success(f"🗑️ 「{del_target}」さんのデータを安全に削除（アーカイブ）しました。")
                st.rerun()
            else:
                st.error(f"Notion側での削除処理に失敗しました。: {res.text}")
    else:
        st.info("登録されているスタッフがいません。")
