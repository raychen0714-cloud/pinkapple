import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import xml.etree.ElementTree as ET

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 級存股戰情室", layout="wide")

# --- 💾 永久記憶系統 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "user_data.json")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "total_div" not in data: data["total_div"] = 0.0
                if "max_price" not in data: data["max_price"] = 1000.0
                if "custom_div_map" not in data: data["custom_div_map"] = {}
                if "held_stocks" not in data: data["held_stocks"] = []
                if "manual_tickers" not in data: data["manual_tickers"] = "878, 919, 918, 0056, 927, 0052, 2409, 6116, 3481"
                return data
        except Exception as e:
            pass
            
    return {
        "total_div": 0.0,
        "max_price": 1000.0,
        "custom_div_map": {"00919.TW": "1.0元", "00918.TW": "1.26元", "0056.TW": "1.0元"},
        "held_stocks": ["00878.TW", "00919.TW", "00918.TW", "0056.TW", "00927.TW"],
        "manual_tickers": "878, 919, 918, 0056, 927, 0052, 2409, 6116, 3481"
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        st.error(f"❌ 存檔失敗: {e}")

if 'app_data' not in st.session_state:
    st.session_state.app_data = load_data()

# --- ⚡ 零延遲引擎：證交所/櫃買中心官方即時 API ---
@st.cache_data(ttl=5) # 只快取 5 秒，確保幾乎零延遲
def fetch_twse_realtime(tickers):
    ex_ch_list = []
    for t in tickers:
        code = t.split('.')[0]
        if '.TW' in t and len(code) >= 4: ex_ch_list.append(f"tse_{code}.tw")
        elif '.TWO' in t and len(code) >= 4: ex_ch_list.append(f"otc_{code}.tw")

    if not ex_ch_list: return {}

    # 證交所 API 要求必須先有 Session 才能抓即時報價，防止機器人
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={'|'.join(ex_ch_list)}&json=1&delay=0"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        session = requests.Session()
        session.get("https://mis.twse.com.tw/stock/index.jsp", headers=headers, timeout=5)
        res = session.get(url, headers=headers, timeout=5)
        data = res.json()
        
        results = {}
        for item in data.get('msgArray', []):
            try:
                code = item.get('c')
                ex = item.get('ex')
                # z: 最近成交價, y: 昨收, v: 累積成交量
                price = item.get('z', item.get('y')) # 如果剛開盤還沒成交，取昨收
                price = float(price) if price != '-' else float(item.get('y'))
                prev_close = float(item.get('y'))
                vol = int(item.get('v', 0))
                
                original_ticker = f"{code}.TW" if ex == 'tse' else f"{code}.TWO"
                results[original_ticker] = {
                    "price": price,
                    "prev_close": prev_close,
                    "vol": vol
                }
            except: continue
        return results
    except Exception as e:
        return {}

# --- 💰 存股配息金庫 ---
st.markdown("### 💰 PRO 級存股配息金庫")
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📥 紀錄本月配息入帳")
    with st.form("add_div_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1: month_input = st.number_input("月份", min_value=1, max_value=12, value=6, step=1)
        with c2: amount_input = st.number_input("入帳金額 (元)", min_value=0, value=0, step=100)
        with c3:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            if st.form_submit_button("➕ 加入總額", use_container_width=True):
                st.session_state.app_data["total_div"] += float(amount_input)
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

# --- 📈 籌碼雷達 ---
@st.cache_data(ttl=3600)
def fetch_twse_institutional_data():
    try:
        url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
        res = requests.get(url, timeout=5)
        data = res.json()
        chip_dict = {}
        for item in data:
            code = item.get("Code")
            try:
                fi_net = float(item.get("ForeignInvestorBuySellAmount", 0).replace(",", ""))
                it_net = float(item.get("InvestmentTrustBuySellAmount", 0).replace(",", ""))
            except: fi_net, it_net = 0, 0

            threshold = 1000000
            if fi_net > threshold and it_net > threshold: status = "🔥 外資投信聯手大買"
            elif fi_net < -threshold and it_net < -threshold: status = "🚨 外資投信聯手倒貨"
            elif fi_net > threshold: status = "📈 外資大量買進"
            elif fi_net < -threshold: status = "⚠️ 外資大量倒貨"
            elif it_net > threshold: status = "💎 投信大量買進"
            elif it_net < -threshold: status = "⚠️ 投信大量倒貨"
            elif fi_net > 0 and it_net > 0: status = "🟢 雙重偏多"
            elif fi_net < 0 and it_net < 0: status = "🔴 雙重偏空"
            elif fi_net > 0: status = "外資買超"
            elif fi_net < 0: status = "外資賣超"
            else: status = "➖ 籌碼中性"
            chip_dict[code] = status
        return chip_dict
    except: return {}

chip_data_map = fetch_twse_institutional_data()

CUSTOM_NAME_MAP = {
    "4958.TW": "臻鼎-KY", "3037.TW": "四欣技", "3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶",
    "00981A.TW": "瑤姊", "00631L.TW": "元大正2", "00685L.TW": "群益正2", "0052.TW": "富邦科技",
    "009816.TW": "凱基台灣TOP50", "0050.TW": "元大台灣50", "0056.TW": "元大高股息",
    "00878.TW": "國泰永續高股息", "00919.TW": "群益精選高息", "00929.TW": "復華台灣科技優息",
    "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息", "00918.TW": "大華優利高填息",
    "00927.TW": "群益半導體收益", "00939.TW": "統一台灣高息動能", "00940.TW": "元大台灣價值高息"
}

MASTER_UNIVERSE = {
    "2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "3711.TW": "日月光投控", 
    "3034.TW": "聯詠", "2379.TW": "瑞昱", "3661.TW": "世芯-KY", "8046.TW": "南電", 
    "3037.TW": "四欣技", "5347.TWO": "世界先進", "6239.TW": "力成", "3131.TWO": "弘塑",
    "3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶", "3008.TW": "大立光",
    "00878.TW": "國泰永續高股息", "0056.TW": "元大高股息", "00919.TW": "群益精選高息", 
    "00929.TW": "復華台灣科技優息", "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息", 
    "00918.TW": "大華優利高填息", "00927.TW": "群益半導體收益", "00881.TW": "國泰台灣5G+"
}

st.sidebar.header("🎛️ 篩選控制台")
current_max = round(float(st.session_state.app_data.get("max_price", 1000.0)), 1)
max_price = st.sidebar.number_input("1. 設定最高價位 (元)", value=current_max, step=10.0)

if round(float(max_price), 1) != current_max:
    st.session_state.app_data["max_price"] = float(max_price)
    save_data(st.session_state.app_data)
    st.rerun()  

st.sidebar.markdown("---")
only_manual = st.sidebar.checkbox("🎯 只看自選標的 (隱藏系統清單)", value=False)
saved_tickers = st.session_state.app_data.get("manual_tickers", "878, 919, 918, 0056, 927, 0052, 2409, 6116, 3481")
manual_tickers_str = st.sidebar.text_input("🔍 2. 手動新增觀察標的", value=saved_tickers)

if manual_tickers_str != saved_tickers:
    st.session_state.app_data["manual_tickers"] = manual_tickers_str
    save_data(st.session_state.app_data)
    st.rerun()

# --- 🧠 雙重融核運算引擎 (即時股價+歷史趨勢) ---
@st.cache_data(ttl=30)  
def fetch_and_analyze(price_limit, manual_input, only_manual_flag):
    tickers_to_fetch = {}
    if not only_manual_flag: tickers_to_fetch.update(MASTER_UNIVERSE.copy())
        
    manual_symbols = []
    if manual_input:
        clean_input = manual_input.replace("，", ",").replace("、", ",").replace(" ", ",")
        for t in [t.strip().upper() for t in clean_input.split(",") if t.strip()]:
            if len(t) <= 3 and t.isdigit(): t = f"00{t}"
            t_symbol = f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t
            name = MASTER_UNIVERSE.get(t_symbol, CUSTOM_NAME_MAP.get(t_symbol, "自選標的"))
            tickers_to_fetch[t_symbol] = name
            manual_symbols.append(t_symbol)
    
    if not tickers_to_fetch: return pd.DataFrame()
    
    # ⚡ [關鍵修改]：先透過官方 API 一次抓取所有即時報價
    realtime_data = fetch_twse_realtime(list(tickers_to_fetch.keys()))
    
    results = [] 
    for ticker, name in tickers_to_fetch.items():
        try:
            is_manual = (ticker in manual_symbols)
            tk = yf.Ticker(ticker)
            
            if name == "自選標的":
                try: 
                    real_name = tk.info.get("shortName")
                    if real_name: name = real_name[:8] + ".." if len(real_name) > 8 else real_name
                except: pass

            yahoo_div_info = "-"
            if is_manual:
                try:
                    divs = tk.dividends
                    if not divs.empty:
                        yahoo_div_info = f"{round(float(divs.iloc[-1]), 3)}元 ({divs.index[-1].strftime('%Y-%m-%d')})"
                except: pass

            # yfinance 現在只用來算均線與量能，不管現價
            hist = tk.history(period="6mo", auto_adjust=False)
            if hist.empty and is_manual and ticker.endswith(".TW"):
                ticker_two = ticker.replace(".TW", ".TWO")
                tk = yf.Ticker(ticker_two)
                hist = tk.history(period="6mo", auto_adjust=False)
                if not hist.empty: ticker = ticker_two 
                    
            if hist.empty or len(hist) < 10: continue

            # ⚡ 注入證交所零延遲報價
            rt_info = realtime_data.get(ticker)
            if rt_info:
                close_px = rt_info['price']
                prev_close = rt_info['prev_close']
                vol = rt_info['vol'] # 單位是張
            else:
                # 備用方案：若官方斷線，退回 yf
                close_px = float(tk.fast_info.last_price) if not np.isnan(float(tk.fast_info.last_price)) else float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2])
                vol = float(hist['Volume'].iloc[-1]) / 1000
                
            if not is_manual and close_px > price_limit: continue
            
            price_change_abs = close_px - prev_close 
            price_change_pct = (price_change_abs / prev_close) * 100 
            if price_change_abs > 0: change_str = f"🔺 +{price_change_pct:.2f}% / +{price_change_abs:.2f}"
            elif price_change_abs < 0: change_str = f"🔻 {price_change_pct:.2f}% / {price_change_abs:.2f}"
            else: change_str = "➖ 0.00% / 0.00"

            vol_5ma = float(hist['Volume'].tail(5).mean()) / 1000
            ma5 = float(hist['Close'].tail(5).mean())   
            ma20 = float(hist['Close'].tail(20).mean())  
            ma60 = float(hist['Close'].tail(60).mean()) if len(hist) >= 60 else 0 
            
            bias = ((close_px - ma20) / ma20) * 100  
            px_up = close_px > prev_close                
            vol_surge = (vol_5ma > 0 and (vol / vol_5ma) >= 2.0)
            
            if ma60 > 0 and close_px > ma5 > ma20 > ma60: trend_status = "🔥 多頭排列" 
            elif ma60 > 0 and close_px < ma5 < ma20 < ma60: trend_status = "🧊 空頭排列" 
            elif ma60 > 0 and close_px > ma60: trend_status = "🔼 站上季線" 
            else: trend_status = "🔽 跌破季線" 

            is_etf = ticker.replace(".TW","").replace(".TWO","").startswith("00")
            if is_etf:
                if trend_status in ["🔽 跌破季線", "🧊 空頭排列"] and bias < -10: note = "💎 跌深可抄底"
                elif trend_status in ["🔥 多頭排列", "🔼 站上季線"]: note = "🟢 趨勢向上"
                else: note = "⚪ 進入整理"
            else:
                if vol_surge and px_up: note = "🐋 疑似大戶進場！"
                elif vol_surge and not px_up: note = "🚨 疑似倒貨！"
                elif px_up and trend_status in ["🔥 多頭排列", "🔼 站上季線"]: note = "🟢 趨勢強勢"
                elif px_up: note = "🟡 溫和上漲"
                else: note = "⚪ 量縮回檔"

            code_only = ticker.replace(".TW", "").replace(".TWO","")
            results.append({
                "is_manual": is_manual,
                "原始代號": ticker,  
                "代號": code_only, 
                "名稱": name,
                "現價": round(close_px, 2), 
                "📈 漲跌": change_str, 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "📊 官方籌碼": chip_data_map.get(code_only, "➖ 上櫃/暫無"),  
                "🤖 系統建議": note,
                "Yahoo配息": yahoo_div_info 
            })
        except: continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["成交量(張)"], ascending=[False]).reset_index(drop=True)
    return df 

st.markdown("---")
st.subheader(f"🔍 PRO 觀察雷達 (最高價 {max_price} 元以下)")
col1, col2 = st.columns([8, 2])
with col2:
    if st.button("🔄 強制刷新零延遲報價", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("官方 MIS 零延遲系統連接中..."):
    final_data = fetch_and_analyze(max_price, manual_tickers_str, only_manual)

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
    
    display_df = final_data[['📌 持有', '原始代號', '標的', '現價', '📈 漲跌', '成交量(張)', '📊 官方籌碼', '趨勢格局', '🤖 系統建議', '💰 最新配息']]
    display_df = display_df.sort_values(by=["📌 持有", "成交量(張)"], ascending=[False, False]).reset_index(drop=True)
    
    def color_tw_stock(val):
        if isinstance(val, str):
            if '🔺' in val: return 'color: #ff4b4b; font-weight: bold;' 
            elif '🔻' in val: return 'color: #09ab3b; font-weight: bold;' 
        return ''

    styled_df = display_df.style.map(color_tw_stock, subset=['📈 漲跌']) if hasattr(display_df.style, "map") else display_df.style.applymap(color_tw_stock, subset=['📈 漲跌'])
    
    edited_df = st.data_editor(
        styled_df, key="portfolio_editor", hide_index=True, use_container_width=True, 
        disabled=["標的", "現價", "📈 漲跌", "📊 官方籌碼", "趨勢格局", "🤖 系統建議"], 
        column_config={
            "📌 持有": st.column_config.CheckboxColumn("📌 持有", width=50),
            "原始代號": None, 
            "標的": st.column_config.TextColumn("標的", width=140), 
            "現價": st.column_config.NumberColumn("現價", format="$%.2f", width=70),
            "📈 漲跌": st.column_config.TextColumn("📈 漲跌", width=120), 
            "成交量(張)": st.column_config.NumberColumn("成交量", width=70),
            "📊 官方籌碼": st.column_config.TextColumn("📊 籌碼", width=120),
            "趨勢格局": st.column_config.TextColumn("趨勢", width=90), 
            "🤖 系統建議": st.column_config.TextColumn("🤖 建議", width=220), 
            "💰 最新配息": st.column_config.TextColumn("💰 配息", width=140) 
        }
    )

    has_changes = False
    current_held = st.session_state.app_data.get("held_stocks", [])
    for i in range(len(display_df)):
        ticker_key = display_df.iloc[i]['原始代號']
        old_held, new_held = bool(display_df.iloc[i]['📌 持有']), bool(edited_df.iloc[i]['📌 持有'])
        if old_held != new_held:
            if new_held and (ticker_key not in current_held): current_held.append(ticker_key)
            elif (not new_held) and (ticker_key in current_held): current_held.remove(ticker_key)
            has_changes = True

        old_div, new_div = str(display_df.iloc[i]['💰 最新配息']), str(edited_df.iloc[i]['💰 最新配息'])
        if old_div != new_div:
            st.session_state.app_data["custom_div_map"][ticker_key] = new_div
            has_changes = True

    if has_changes:
        st.session_state.app_data["held_stocks"] = current_held
        save_data(st.session_state.app_data)       
        st.rerun()
