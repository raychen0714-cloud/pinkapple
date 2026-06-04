import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="戰情室", layout="wide")

# --- 💾 永久記憶系統 (寫入本機檔案) ---
DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_div": 0.0,
        "max_price": 1000,
        "custom_div_map": {
            "00919.TW": "1.0元 (請手動更新日期)",
            "00918.TW": "1.26元 (請手動更新日期)",
            "0056.TW": "1.0元 (2026-04-23)" 
        }
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'app_data' not in st.session_state:
    st.session_state.app_data = load_data()

# --- 💰 存股配息金庫 (全新頂部 UI) ---
st.markdown("### 💰 存股配息金庫")
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📥 紀錄本月配息入帳")
    with st.form("add_div_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1:
            month_input = st.number_input("月份", min_value=1, max_value=12, value=6, step=1)
        with c2:
            amount_input = st.number_input("入帳金額 (元)", min_value=0, value=0, step=100)
        with c3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            submitted_div = st.form_submit_button("➕ 加入總額", use_container_width=True)
            if submitted_div:
                st.session_state.app_data["total_div"] += amount_input
                save_data(st.session_state.app_data)
                st.rerun()

with col_right:
    st.markdown("#### 🏆 總領配息累計")
    st.markdown(f"<h1 style='color: #1e3c72; font-weight: 900; font-size: 48px;'>${st.session_state.app_data['total_div']:,.0f}</h1>", unsafe_allow_html=True)
    
    # 🔥 全新：隱藏版的總額校正開關
    with st.expander("🛠️ 不小心輸入錯誤？點此手動校正總額"):
        correct_val = st.number_input("直接輸入正確的總金額", value=int(st.session_state.app_data['total_div']), step=1000)
        if st.button("💾 強制覆寫總額", use_container_width=True):
            st.session_state.app_data["total_div"] = float(correct_val)
            save_data(st.session_state.app_data)
            st.rerun()

st.markdown("---")

# --- 📝 專屬自訂名稱字典 ---
CUSTOM_NAME_MAP = {
    "0050.TW": "元大台灣50",
    "0052.TW": "富邦科技",
    "00692.TW": "富邦公司治理",
    "00713.TW": "元大台灣高息低波",
    "4958.TW": "臻鼎-KY"
}

# --- 📂 1. 定義標的池 ---
STOCK_UNIVERSE = {
    "半導體": {
        "2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "3711.TW": "日月光投控", 
        "3034.TW": "聯詠", "2379.TW": "瑞昱", "3661.TW": "世芯-KY", "8046.TW": "南電", 
        "3037.TW": "欣興", "5347.TW": "世界先進", "6239.TW": "力成", "3131.TW": "弘塑"
    },
    "光電與面板": {
        "3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶", "3008.TW": "大立光"
    }
}

ETF_UNIVERSE = {
    "高股息": {
        "00878.TW": "國泰永續高股息", "0056.TW": "元大高股息", "00919.TW": "群益精選高息", 
        "00929.TW": "復華台灣科技優息", "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息30", 
        "00918.TW": "大華優利高填息30"
    },
    "半導體與科技": {
        "00927.TW": "群益半導體收益", "00881.TW": "國泰台灣5G+", "00891.TW": "中信關鍵半導體",
        "00935.TW": "野村臺灣新科技50"
    }
}

# --- 🎛️ 2. 動態篩選控制台 (UI) ---
st.sidebar.header("🎛️ 篩選控制台")
target_type = st.sidebar.radio("1. 選擇標的類型", ["個股", "ETF"])

if target_type == "個股":
    selected_categories = st.sidebar.multiselect("2. 選擇產業板塊", list(STOCK_UNIVERSE.keys()), default=["半導體", "光電與面板"])
    active_universe = STOCK_UNIVERSE
else:
    selected_categories = st.sidebar.multiselect("2. 選擇 ETF 類型", list(ETF_UNIVERSE.keys()), default=["高股息", "半導體與科技"])
    active_universe = ETF_UNIVERSE

current_max = st.session_state.app_data.get("max_price", 1000)
max_price = st.sidebar.number_input("3. 設定最高價位 (元)", value=current_max, step=10)

if max_price != current_max:
    st.session_state.app_data["max_price"] = max_price
    save_data(st.session_state.app_data)

st.sidebar.markdown("---")
only_manual = st.sidebar.checkbox("🎯 只看自選標的 (隱藏上方系統清單)", value=False)

manual_tickers_str = st.sidebar.text_input(
    "🔍 4. 手動新增觀察標的", 
    value="878, 919, 918, 0056, 927, 0052, 2409, 6116", 
    placeholder="如: 878, 56, 3131"
)

st.sidebar.markdown("---")
with st.sidebar.form("update_div_form"):
    st.markdown("### ✏️ 5. 瞬間更新最新配息")
    st.caption("改版為秒速更新，不需重新連線 Yahoo")
    update_ticker = st.text_input("輸入代號 (如 00919)")
    update_amt = st.text_input("配息金額 (如 1.0)")
    update_date = st.text_input("除息日期 (如 2026-06-15)")
    
    submitted_update = st.form_submit_button("⚡ 瞬間強制更新", use_container_width=True)
    if submitted_update and update_ticker and update_amt and update_date:
        t_key = f"{update_ticker}.TW" if not update_ticker.endswith(".TW") else update_ticker
        st.session_state.app_data["custom_div_map"][t_key] = f"{update_amt}元 ({update_date})"
        save_data(st.session_state.app_data)
        st.rerun()

# --- 🧠 3. 核心運算引擎 ---
@st.cache_data(ttl=30) 
def fetch_and_analyze(categories, universe_dict, price_limit, current_type, manual_input, only_manual_flag):
    tickers_to_fetch = {}
    
    if not only_manual_flag:
        for cat in categories:
            tickers_to_fetch.update(universe_dict[cat].copy())
        
    manual_symbols = []
    if manual_input:
        clean_input = manual_input.replace("，", ",").replace("、", ",").replace(" ", ",")
        raw_tickers = [t.strip().upper() for t in clean_input.split(",") if t.strip()]
        for t in raw_tickers:
            if len(t) <= 3 and t.isdigit(): t = f"00{t}"
            elif len(t) == 4 and (t.endswith('R') or t.endswith('L')) and t[0] !=
