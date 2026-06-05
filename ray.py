import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import xml.etree.ElementTree as ET # 🔥 新增：用來解析即時新聞的內建套件

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

# --- 📰 即時新聞攔截引擎 (完全免費) ---
@st.cache_data(ttl=1800) # 每半小時自動更新一次新聞
def fetch_realtime_news(keyword):
    """利用 Google 新聞 RSS 抓取指定關鍵字的最新動態"""
    try:
        url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        res = requests.get(url, timeout=5)
        root = ET.fromstring(res.content)
        news_list = []
        for item in root.findall('.//channel/item')[:5]: # 只取最新前 5 則
            title = item.find('title').text
            link = item.find('link').text
            # 簡單清理新聞標題後面的媒體名稱 (例如 " - Yahoo奇摩股市")
            clean_title = title.rsplit(" - ", 1)[0] 
            news_list.append({"title": clean_title, "link": link})
        return news_list
    except:
        return [{"title": "目前無法獲取新聞，請稍後再試", "link": "#"}]

# --- 📈 證交所官方開放資料：籌碼雷達引擎 ---
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
            except:
                fi_net, it_net = 0, 0

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
    except:
        return {}

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
                        k_msg = "⚠️ 上影線"
                    elif dn_shadow > body * 1.5 and dn_shadow > up_shadow * 1.5:
                        k_msg = "💡 下影線"
                note = f"[{k_msg}] {note}"
            except: pass

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
                "📊 官方籌
