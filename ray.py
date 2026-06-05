import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests # 🔥 新增：用來抓取證交所官方資料的模組

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 級存股戰情室", layout="wide")

# --- 💾 永久記憶系統 (絕對路徑鎖死版) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "user_data.json")

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_div": 0.0,
        "max_price": 1000,
        "custom_div_map": {
            "00919.TW": "1.0元",
            "00918.TW": "1.26元",
            "0056.TW": "1.0元" 
        },
        "held_stocks": ["00878.TW", "00919.TW", "00918.TW", "0056.TW", "00927.TW"]
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'app_data' not in st.session_state:
    st.session_state.app_data = load_data()

if st.session_state.get("show_save_success", False):
    st.toast("💾 戰情室設定已成功同步並永久儲存！", icon="✅")
    st.session_state.show_save_success = False

# --- 💰 存股配息金庫 (頂部 UI) ---
st.markdown("### 💰 PRO 級存股配息金庫")
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
    
    with st.expander("🛠️ 不小心輸入錯誤？點此手動校正總額"):
        correct_val = st.number_input("直接輸入正確的總金額", value=int(st.session_state.app_data['total_div']), step=1000)
        if st.button("💾 強制覆寫總額", use_container_width=True):
            st.session_state.app_data["total_div"] = float(correct_val)
            save_data(st.session_state.app_data)
            st.rerun()

st.markdown("---")

# --- 📈 證交所官方開放資料：籌碼雷達引擎 ---
@st.cache_data(ttl=3600) # 快取 1 小時，避免重複抓取
def fetch_twse_institutional_data():
    """使用台灣證交所官方 Open Data API，免費、即時且絕對準確"""
    try:
        url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
        res = requests.get(url, timeout=5)
        data = res.json()
        chip_dict = {}
        for item in data:
            code = item.get("Code")
            try:
                # 取得外資與投信的買賣超股數 (去掉逗號轉數字)
                fi_net = float(item.get("ForeignInvestorBuySellAmount", 0).replace(",", ""))
                it_net = float(item.get("InvestmentTrustBuySellAmount", 0).replace(",", ""))
            except:
                fi_net, it_net = 0, 0

            # 籌碼判斷標準 (100萬股 = 1000張)
            threshold = 1000000
            
            if fi_net > threshold and it_net > threshold:
                status = "🔥 外資投信聯手大買"
            elif fi_net < -threshold and it_net < -threshold:
                status = "🚨 外資投信聯手倒貨"
            elif fi_net > threshold:
                status = "📈 外資大量買進"
            elif fi_net < -threshold:
                status = "⚠️ 外資大量倒貨"
            elif it_net > threshold:
                status = "💎 投信大量買進"
            elif it_net < -threshold:
                status = "⚠️ 投信大量倒貨"
            elif fi_net > 0 and it_net > 0:
                status = "🟢 雙重偏多"
            elif fi_net < 0 and it_net < 0:
                status = "🔴 雙重偏空"
            elif fi_net > 0:
                status = "外資買超"
            elif fi_net < 0:
                status = "外資賣超"
            else:
                status = "➖ 籌碼中性"
            
            chip_dict[code] = status
        return chip_dict
    except:
        return {}

# 啟動並獲取官方籌碼資料
chip_data_map = fetch_twse_institutional_data()

# --- 📝 專屬自訂名稱字典 ---
CUSTOM_NAME_MAP = {
    "0050.TW": "元大台灣50",
    "0052.TW": "富邦科技",
    "00692.TW": "富邦公司治理",
    "00713.TW": "元大台灣高息低波",
    "4958.TW": "臻鼎-KY",
    "3037.TW": "四欣技" 
}

# --- 📂 1. 定義標的池 ---
STOCK_UNIVERSE = {
    "半導體": {
        "2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "3711.TW": "日月光投控", 
        "3034.TW": "聯詠", "2379.TW": "瑞昱", "3661.TW": "世芯-KY", "8046.TW": "南電", 
        "3037.TW": "四欣技", "5347.TWO": "世界先進", "6239.TW": "力成", "3131.TWO": "弘塑"
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
only_manual = st.sidebar.checkbox("🎯 只看自選標的 (隱藏系統清單)", value=False)

manual_tickers_str = st.sidebar.text_input(
    "🔍 4. 手動新增觀察標的", 
    value="878, 919, 918, 0056, 927, 0052, 2409, 6116", 
    placeholder="如: 878, 56, 3131"
)

# --- 🧠 3. 核心運算引擎 ---
@st.cache_data(ttl=60) 
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
            elif len(t) == 4 and (t.endswith('R') or t.endswith('L')) and t[0] != '0': t = f"00{t}"
            t_symbol = f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t
            
            display_name = "自選標的"
            for cat_key, stocks in STOCK_UNIVERSE.items():
                if t_symbol in stocks: display_name = stocks[t_symbol]
            for cat_key, etfs in ETF_UNIVERSE.items():
                if t_symbol in etfs: display_name = etfs[t_symbol]
                
            tickers_to_fetch[t_symbol] = display_name
            manual_symbols.append(t_symbol)
    
    if not tickers_to_fetch: return pd.DataFrame()
    results = [] 
    
    for ticker, name in tickers_to_fetch.items():
        try:
            is_manual = (ticker in manual_symbols)
            tk = yf.Ticker(ticker)
            
            if name == "自選標的":
                if ticker in CUSTOM_NAME_MAP: name = CUSTOM_NAME_MAP[ticker]
                else:
                    try:
                        real_name = tk.info.get("shortName")
                        if real_name: name = real_name
                    except: pass

            yahoo_div_info = "-"
            if is_manual:
                try:
                    divs = tk.dividends
                    if not divs.empty:
                        last_div = round(float(divs.iloc[-1]), 3)
                        last_date = divs.index[-1].strftime("%Y-%m-%d")
                        yahoo_div_info = f"{last_div}元 ({last_date})"
                except: pass

            hist = tk.history(period="6mo", auto_adjust=False)
            if hist.empty and is_manual and ticker.endswith(".TW"):
                ticker_two = ticker.replace(".TW", ".TWO")
                tk = yf.Ticker(ticker_two)
                hist = tk.history(period="6mo", auto_adjust=False)
                if not hist.empty: ticker = ticker_two 
                    
            if hist.empty: continue
            hist = hist.replace([np.inf, -np.inf], np.nan).dropna(subset=['Close', 'Volume'])
            
            if len(hist) < 10 and is_manual: continue
            elif len(hist) < 60 and not is_manual: continue
            
            try:
                close_px = float(tk.fast_info.last_price)
                if np.isnan(close_px) or close_px <= 0: close_px = float(hist['Close'].iloc[-1])
            except: close_px = float(hist['Close'].iloc[-1])
                
            if not is_manual and close_px > price_limit: continue
            prev_px = float(hist['Close'].iloc[-2])
            vol = float(hist['Volume'].iloc[-1]) / 1000  
            if not is_manual and vol < 1000 and current_type == "個股": continue 

            vol_5ma = float(hist['Volume'].tail(5).mean()) / 1000
            ma5 = float(hist['Close'].tail(5).mean())    
            ma20 = float(hist['Close'].tail(20).mean())  
            ma60 = float(hist['Close'].tail(60).mean()) if len(hist) >= 60 else 0 
            
            bias = ((close_px - ma20) / ma20) * 100  
            px_up = close_px > prev_px               
            vol_surge = (vol_5ma > 0 and (vol / vol_5ma) >= 2.0)
            
            if ma60 > 0 and close_px > ma5 > ma20 > ma60: trend_status = "🔥 多頭排列" 
            elif ma60 > 0 and close_px < ma5 < ma20 < ma60: trend_status = "🧊 空頭排列" 
            elif ma60 > 0 and close_px > ma60: trend_status = "🔼 站上季線" 
            elif ma60 == 0: trend_status = "📈 新股觀察"
            else: trend_status = "🔽 跌破季線" 

            if current_type == "ETF" or (is_manual and ticker.replace(".TW","").replace(".TWO","").startswith("00")):
                if trend_status in ["🔽 跌破季線", "🧊 空頭排列"] and bias < -10:
                    note = "💎 跌深殖利率浮現，可抄底"
                elif trend_status in ["🔥 多頭排列", "🔼 站上季線"]:
                    note = "🟢 趨勢向上，適合佈局"
                else: note = "⚪ 進入整理，保持觀望"
            else:
                if vol_surge and px_up: note = "🐋 疑似大戶進場！"
                elif vol_surge and not px_up: note = "🚨 疑似倒貨，控管風險！"
                elif px_up and trend_status in ["🔥 多頭排列", "🔼 站上季線"]: note = "🟢 趨勢強勢"
                elif px_up: note = "🟡 溫和上漲"
                else: note = "⚪ 量縮回檔"
                
            if bias > 20: note = "🔥 短線過熱，留意獲利了結"

            # K棒型態辨識
            try:
                O = float(hist['Open'].iloc[-1])
                H = max(float(hist['High'].iloc[-1]), close_px)
                L = min(float(hist['Low'].iloc[-1]), close_px)
                C = close_px

                body = abs(C - O)
                up_shadow = H - max(O, C)
                dn_shadow = min(O, C) - L
                tr = H - L

                k_msg = "➖"
                if tr > 0:
                    if body / tr >= 0.6:
                        if C >= O: k_msg = "🚀 紅K"
                        else: k_msg = "🔻 黑K"
                    elif up_shadow > body * 1.5 and up_shadow > dn_shadow * 1.5:
                        k_msg = "⚠️ 長上影線"
                    elif dn_shadow > body * 1.5 and dn_shadow > up_shadow * 1.5:
                        k_msg = "💡 長下影線"
                note = f"[{k_msg}] {note}"
            except: pass

            # 🔥 將官方籌碼對應至個股
            code_only = ticker.replace(".TW", "").replace(".TWO","")
            current_chip = chip_data_map.get(code_only, "➖ 上櫃/暫無")

            results.append({
                "is_manual": is_manual,
                "原始代號": ticker,  
                "代號": code_only, 
                "名稱": name,
                "現價": round(close_px, 2), 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "📊 官方籌碼": current_chip,  # 新增籌碼欄位
                "🤖 系統建議": note,
                "Yahoo配息": yahoo_div_info 
            })
        except: continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["成交量(張)"], ascending=[False])
        df.reset_index(drop=True, inplace=True)
    return df 

# --- 📊 4. 畫面渲染 ---
st.subheader(f"🔍 PRO 觀察雷達 (最高價 {max_price} 元以下)")

with st.spinner("真實證券報價、官方籌碼與配息資料同步中..."):
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price, target_type, manual_tickers_str, only_manual)

if not final_data.empty:
    def assign_final_dividend(row):
        t_key = row['原始代號']
        if t_key in st.session_state.app_data["custom_div_map"]:
            return st.session_state.app_data["custom_div_map"][t_key]
        return row['Yahoo配息']

    final_data['💰 最新配息'] = final_data.apply(assign_final_dividend, axis=1)
    
    held_list = st.session_state.app_data.get("held_stocks", [])
    final_data['📌 持有'] = final_data['原始代號'].apply(lambda x: x in held_list)
    final_data['標的'] = final_data['代號'].astype(str) + " " + final_data['名稱']
    
    # 重新排列欄位，把籌碼面拉到顯眼的位置
    display_df = final_data[['📌 持有', '原始代號', '標的', '📊 官方籌碼', '🤖 系統建議', '現價', '成交量(張)', '趨勢格局', '💰 最新配息']]
    display_df = display_df.sort_values(by=["📌 持有", "成交量(張)"], ascending=[False, False]).reset_index(drop=True)
    
    # 啟動 PRO 級試算表編輯器
    edited_df = st.data_editor(
        display_df,
        key="portfolio_editor", 
        hide_index=True,
        use_container_width=False, 
        # 鎖定報價與抓下來的官方籌碼，保留持股、成交量與配息的手動修改權限
        disabled=["標的", "📊 官方籌碼", "🤖 系統建議", "現價", "趨勢格局"], 
        column_config={
            "📌 持有": st.column_config.CheckboxColumn("📌 持有"),
            "原始代號": None, 
            "標的": st.column_config.TextColumn("標的"),
            "📊 官方籌碼": st.column_config.TextColumn("📊 官方籌碼 (盤後同步)"),
            "🤖 系統建議": st.column_config.TextColumn("🤖 系統建議"), 
            "現價": st.column_config.NumberColumn("現價"),
            "成交量(張)": st.column_config.NumberColumn("成交量(張) (✎ 手動覆寫真實量)"),
            "趨勢格局": st.column_config.TextColumn("趨勢格局"),
            "💰 最新配息": st.column_config.TextColumn("💰 最新配息 (✎ 雙擊修改)") 
        }
    )

    if "portfolio_editor" in st.session_state:
        edited_rows = st.session_state["portfolio_editor"].get("edited_rows", {})
        if edited_rows:
            has_changes = False
            current_held = st.session_state.app_data.get("held_stocks", [])
            
            for str_idx, changes in edited_rows.items():
                row_idx = int(str_idx)
                ticker_key = display_df.iloc[row_idx]['原始代號']
                
                if "📌 持有" in changes:
                    is_checked = changes["📌 持有"]
                    if is_checked and (ticker_key not in current_held):
                        current_held.append(ticker_key)
                    elif (not is_checked) and (ticker_key in current_held):
                        current_held.remove(ticker_key)
                    st.session_state.app_data["held_stocks"] = current_held
                    has_changes = True
                
                if "💰 最新配息" in changes:
                    new_val = changes["💰 最新配息"]
                    st.session_state.app_data["custom_div_map"][ticker_key] = new_val
                    has_changes = True
                    
            if has_changes:
                save_data(st.session_state.app_data)       
                st.session_state.show_save_success = True  
                st.rerun()                                 

else:
    st.info("請確認手動輸入代號後是否已按下鍵盤上的『確認/Enter』鍵，或放寬篩選產業。")
