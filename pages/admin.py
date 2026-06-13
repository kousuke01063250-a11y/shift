import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
import hashlib  # 🔒 パスワードハッシュ化用

# 最適化ライブラリのインポートチェック
try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False

# ページ設定
st.set_page_config(page_title="シフト確認ダッシュボード", layout="wide")

# ==========================================
# 🔒 確実なパスワード認証機能 (ハッシュ化版)
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

def check_password():
    if st.session_state["password_correct"]:
        return True
    st.title("🔒 管理者認証")
    input_password = st.text_input("パスワードを入力してください", type="password")
    if input_password:
        # 入力されたパスワードをSHA-256でハッシュ化
        hashed_input = hashlib.sha256(input_password.encode()).hexdigest()
        # 「admin123」のハッシュ値
        target_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
        
        if hashed_input == target_hash:
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
all_positions_set = set() 

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
st.title("🤖 🚀 数理最適化シフト自動生成システム (公平性分配モデル)")
selected_day_index = st.selectbox("シフトを自動生成する曜日を選択してください", range(7), format_func=lambda x: f"{target_dates[x]} ({week_days[x]}曜日)")
selected_date_str = target_dates[selected_day_index]

# 🎯 条件設定
st.markdown("### 🎯 1. 現場の総戦闘力・人件費の調整")
col_tgt1, col_tgt2 = st.columns(2)
with col_tgt1:
    min_strength_target = st.number_input("📉 必要な最低総戦闘力", min_value=0, value=3, step=1)
with col_tgt2:
    max_strength_target = st.number_input("📈 上限の総戦闘力", min_value=0, value=8, step=1)

# ✨ 新設：アプローチA「希望シフトの目標採用率（公平性）」の設定UI
st.markdown("### ⚖️ 2. スタッフ間の公平性設定（ベテラン偏重の防止）")
target_fill_rate = st.slider(
    "📊 希望シフトに対する目標採用率 (%)", 
    min_value=10, max_value=100, value=70, step=5,
    help="提出された希望コマ数に対して、全員が一律で何%くらいシフトに入れるようにするかを調整します。低すぎると人手不足になり、高すぎると人件費が過剰になります。"
) / 100.0

# ポジションごとの最低必要人数の動的UI
st.markdown("### 🛠️ 3. ポジションごとの最低必要人数設定")
position_requirements = {}
if all_positions:
    cols = st.columns(len(all_positions))
    for idx, pos in enumerate(all_positions):
        with cols[idx]:
            position_requirements[pos] = st.number_input(f"👥 {pos}の最低必要人数", min_value=0, value=1, step=1)
else:
    st.info("※Notionのスタッフデータベースに職種が登録されていません。最下部から追加してください。")

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
            with st.spinner("数理最適化ソルバーが公平性を計算しつつ、シフトを自動生成中..."):
                staff_list = list(staff_info_dict.keys())
                
                # 出勤可能マトリクス と 各自の希望総コマ数(WishCount)の計算
                A = {i: {t: 0 for t in slots_without_last} for i in staff_list}
                wish_counts = {i: 0 for i in staff_list}
                
                for _, row in df_filtered.iterrows():
                    name = row["純粋な名前"]
                    for t in slots_without_last:
                        slot_dt = datetime.strptime(f"{selected_date_str} {t}", "%Y-%m-%d %H:%M")
                        if row["開始時刻"] <= slot_dt < row["終了時刻"]:
                            if name in A: 
                                A[name][t] = 1

                for i in staff_list:
                    wish_counts[i] = sum(A[i][t] for t in slots_without_last)

                # 問題定義
                prob = pulp.LpProblem("Shift_Fair_Position_Optimization", pulp.LpMinimize)
                
                # 決定変数
                x = pulp.LpVariable.dicts("assign", ((i, t) for i in staff_list for t in slots_without_last), cat='Binary')
                y = pulp.LpVariable.dicts("pos_assign", ((i, p, t) for i in staff_list for p in all_positions for t in slots_without_last), cat='Binary')
                
                # スラック変数（制約緩和用）
                slack_under = pulp.LpVariable.dicts("slack_under", slots_without_last, lowBound=0, cat='Continuous')
                slack_over = pulp.LpVariable.dicts("slack_over", slots_without_last, lowBound=0, cat='Continuous')
                slack_pos = pulp.LpVariable.dicts("slack_pos", ((p, t) for p in all_positions for t in slots_without_last), lowBound=0, cat='Continuous')
                
                # ✨ 公平性用のスラック変数（目標充填率からのズレ）
                slack_fair_under = pulp.LpVariable.dicts("fair_under", staff_list, lowBound=0, cat='Continuous')
                slack_fair_over = pulp.LpVariable.dicts("fair_over", staff_list, lowBound=0, cat='Continuous')

                # 目的関数（最優先：現場の人数・戦闘力、次点：全員の公平性、最下位：総出勤数の抑制）
                prob += (
                    pulp.lpSum(slack_under[t] * 2000 + slack_over[t] * 20 for t in slots_without_last) +
                    pulp.lpSum(slack_pos[p, t] * 1000 for p in all_positions for t in slots_without_last) +
                    pulp.lpSum((slack_fair_under[i] + slack_fair_over[i]) * 300 for i in staff_list if wish_counts[i] > 0) + # ✨ 公平性ペナルティ
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
                        
                        # 4. 1人1ポジションの掛け持ち禁止
                        prob += pulp.lpSum(y[i, p, t] for p in all_positions) == x[i, t]
                        
                        # 5. スキルを保有していないポジションへの配置禁止
                        for p in all_positions:
                            if p not in staff_info_dict[i]["skills"]:
                                prob += y[i, p, t] == 0

                # ✨ 6. 公平性均衡制約の追加
                for i in staff_list:
                    if wish_counts[i] > 0:
                        actual_assigned_slots = pulp.lpSum(x[i, t] for t in slots_without_last)
                        target_assigned_slots = wish_counts[i] * target_fill_rate
                        prob += actual_assigned_slots == target_assigned_slots - slack_fair_under[i] + slack_fair_over[i]

                # ソルバー実行
                prob.solve(pulp.PULP_CBC_CMD(msg=False))
                
                # 結果のデコード
                opt_records = []
                staff_actual_counts = {i: 0 for i in staff_list}
                
                for i in staff_list:
                    current_pos = None
                    start_t = None
                    for idx, t in enumerate(slots_without_last):
                        if pulp.value(x[i, t]) == 1:
                            staff_actual_counts[i] += 1
                            
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
                
                # スタッフごとの採用結果まとめ（公平性の検証用）
                summary_data = []
                for i in staff_list:
                    if wish_counts[i] > 0:
                        rate = int((staff_actual_counts[i] / wish_counts[i]) * 100)
                        summary_data.append({
                            "スタッフ名": i, "戦闘力": staff_info_dict[i]["power"],
                            "希望コマ数": wish_counts[i], "採用コマ数": staff_actual_counts[i], "実際の採用率": f"{rate}%"
                        })
                st.session_state["opt_staff_summary"] = pd.DataFrame(summary_data)
                
                # タイムラインデータの生成
                opt_sim_data = []
                for t in slots_without_last:
                    t_power = sum(staff_info_dict[i]["power"] for i in staff_list if pulp.value(x[i, t]) == 1)
                    is_safe = min_strength_target <= t_power <= max_strength_target
                    status_str = "🟢 適正" if is_safe else ("🚨 戦力不足" if t_power < min_strength_target else "⚠️ コスト過剰")
                    opt_sim_data.append({
                        "時間帯": t, "現在の総戦闘力": t_power, "下限目標": min_strength_target, "上限目標": max_strength_target, "判定結果": status_str
                    })
                st.session_state["opt_sim"] = pd.DataFrame(opt_sim_data)
                st.success("🎉 ベテラン偏重を回避し、公平に分配した最適化シフトの生成が完了しました！")

# ==========================================
# 📈 4. 最適化結果のダッシュボード表示
# ==========================================
if st.session_state.get("opt_df") is not None and st.session_state.get("opt_sim") is not None:
    df_opt = st.session_state["opt_df"]
    df_opt_sim = st.session_state["opt_sim"]
    
    st.markdown("---")
    st.subheader("🏆 生成された最適化シフトの評価")
    
    # ✨ 新設：各自に公平に割り振られているか一目でわかる検証テーブル
    st.markdown("#### ⚖️ スタッフ別・希望シフト採用率の平準化ステータス")
    if st.session_state.get("opt_staff_summary") is not None:
        st.dataframe(st.session_state["opt_staff_summary"], use_container_width=True)
        
    st.markdown("### 📈 最適化後の総戦闘力タイムライン推移")
    fig_opt_line = px.line(df_opt_sim, x="時間帯", y=["現在の総戦闘力", "下限目標", "上限目標"], title="最適化アサイン後の総戦闘力推移", line_shape="hv")
    st.plotly_chart(fig_opt_line, use_container_width=True)
    
    st.markdown("### 📅 確定自動生成シフト（ポジション別色分けガントチャート）")
    if not df_opt.empty:
        fig_opt_gantt = px.timeline(df_opt, x_start="開始", x_end="終了", y="表示名", color="ポジション", text="ポジション", title="時間帯別の担当ポジション可視化")
        fig_opt_gantt.update_yaxes(autorange="reversed")
        fig_opt_gantt.update_layout(xaxis=dict(title="時間帯", tickformat="%H:%M"))
        st.plotly_chart(fig_opt_gantt, use_container_width=True)
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
# 👥 5. スタッフアカウント管理
# ==========================================
st.markdown("---")
st.header("👥 スタッフアカウント管理")
col_s1, col_s2 = st.columns(2)

with col_s1:
    st.subheader("➕ スタッフの新規追加")
    new_staff_name = st.text_input("追加するスタッフの氏名を入力してください", placeholder="例：山田 太郎", key="s_add_name")
    new_staff_power = st.number_input("このスタッフの戦闘力（点数）を設定してください", min_value=1, value=3, step=1, key="s_add_power")
    
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
