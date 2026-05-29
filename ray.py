import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import altair as alt
import requests

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="ETF 投資戰情室", layout="wide")

# 自定義 CSS (移除了一些花俏的閃爍特效，讓視覺更穩定)
st.markdown("""
    <style>
    [data-testid="stMetricDelta"] svg { fill: red; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; }
    
    .news-box { background-color: #f0f7ff; border-left: 6px solid #4a90e2; padding: 20px; border-radius: 8px; margin-bottom: 25px; box-shadow: 1px 1px 4px rgba(0,0,0,0.05); }
    
    /* 三拼損益與領息橫列大看板樣式 */
    .triple-box { background-color: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; padding: 15px; display: flex; flex-wrap: wrap; justify-content: space-around; align-items: center; margin-bottom: 10px; box-shadow: 2px 2px 8px rgba(0,0,0,0.04); gap: 10px; }
    .triple-col { flex: 1 1 22%; min-width: 140px; text-align: center; padding: 10px 0; }
    .triple-title { font-size: 14px; color: #757575; font-weight: bold; margin-bottom: 5px; }
    .triple-val-r { font-size: 28px; font-weight: 900; color: #b71c1c; font-family: Arial, sans-serif; line-height: 1.1; }
    .triple-val-g { font-size: 28px; font-weight: 900; color: #2e7d32; font-family: Arial, sans-serif; line-height: 1.1; }
    .triple-val-gold { font-size: 28px; font-weight: 900; color: #f39c12; font-family: Arial, sans-serif; line-height: 1.1; }
    .triple-pct-r { font-size: 14px; font-weight: bold; color: #b71c1c; margin-top: 5px; }
    .triple-pct-g { font-size: 14px; font-weight: bold; color: #2e7d32; margin-top: 5px; }
    
    .blue-box { background-color: #f0f8ff; border-radius: 12px; padding: 15px; border: 2px solid #90caf9; }
    .triple-val-blue { font-size: 28px; font-weight: 900; color: #1565c0; font-family: Arial, sans-serif; line-height: 1.1; }

    .month-card { background-color: #e9ecef; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 10px; border: 1px solid #ced4da; }
    .month-title { font-size: 20px; font-weight: bold; color: #495057; }
    .month-amount { font-size: 28px; font-weight: bold; color: #d9534f; margin: 10px 0; }
    
    div.stButton > button { font-weight: bold; border-radius: 8px; }
    .auto-refresh-box { background-color: #f0f7ff; border: 1px solid #cce5ff; border-radius: 8px; padding: 15px; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 系統設定與資料庫 ---
SETTINGS_FILE = 'settings.json'

PASSIVE_ETFS = {
    "0050": "0050 元大台灣50", "0056": "0056 元大高股息", "00878": "00878 國泰永續高股息", 
    "00891": "00891 中信關鍵半導體", "00927": "00927 群益半導體收益", "2330": "2330 台積電", 
    "2454": "2454 聯發科", "2317": "2317 鴻海", "3481": "3481 群創", "2303": "2303 聯電"
}
ACTIVE_ETFS = {"00981A": "00981A 主動統一台股增長", "00982A": "00982A 主動群益科技創新"}
ETF_NAME_DB = {**PASSIVE_ETFS, **ACTIVE_ETFS}

DIVIDEND_SCHEDULE = {
    "0050.TW": [1, 7], "0056.TW": [1, 4, 7, 10], "00878.TW": [2, 5, 8, 11],
    "00891.TW": [2, 5, 8, 11], "00927.TW": [1, 4, 7, 10]
}
DIVIDEND_DB = {
    "0056.TW": {"v": 1.00, "d": "2026-04-16", "p": "2026-05-15"}, 
    "00927.TW": {"v": 0.94, "d": "2026-04-18", "p": "2026-05-15"},  
    "00878.TW": {"v": 0.66, "d": "2026-05-19", "p": "2026-06-16"}
}
ETF_CONSTITUENTS_DB = {
    "00878.TW": [{"name": "聯發科", "weight": 5.5}, {"name": "國泰金", "weight": 5.1}, {"name": "聯電", "weight": 4.2}, {"name": "其他", "weight": 85.2}],
    "00927.TW": [{"name": "台積電", "weight": 31.2}, {"name": "聯發科", "weight": 15.5}, {"name": "聯電", "weight": 6.5}, {"name": "其他", "weight": 46.8}]
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    
    return {
        "etfs": [
            {"symbol": "00878.TW", "name": "00878 國泰永續高股息", "holdings": 22.0, "cost": 24.60, "pledged_shares": 0.0},
            {"symbol": "00927.TW", "name": "00927 群益半導體收益", "holdings": 20.0, "cost": 28.65, "pledged_shares": 0.0},
            {"symbol": "2303.TW", "name": "2303 聯電", "holdings": 5.0, "cost": 50.00, "pledged_shares": 0.0}
        ], 
        "pledge": {"borrowed_amount": 0},
        "watchlist": [],
        "notes": "在此輸入您的投資備忘錄..." 
    }

def save_to_json(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if 'my_data' not in st.session_state: 
    st.session_state.my_data = load_settings()

if 'total_received_divs' not in st.session_state.my_data:
    st.session_state.my_data['total_received_divs'] = 0.0
if 'notes' not in st.session_state.my_data:
    st.session_state.my_data['notes'] = "在此輸入您的投資備忘錄..."

for etf in st.session_state.my_data['etfs']:
    if 'pledged_shares' not in etf: etf['pledged_shares'] = 0.0
save_to_json(st.session_state.my_data)

# --- 🚀 Callback 函數區 ---
def auto_fill_etf_name():
    raw_sym = st.session_state.get('add_sym_bot', '')
    clean_sym = raw_sym.strip().upper().replace(".TW", "")
    if clean_sym:
        st.session_state.add_name_bot = ETF_NAME_DB.get(clean_sym, f"{clean_sym} ETF")
    else:
        st.session_state.add_name_bot = ""

def add_new_etf_bot():
    raw_sym = st.session_state.get('add_sym_bot', '')
    new_name = st.session_state.get('add_name_bot', '')
    new_h = st.session_state.get('add_h_bot', 0.0)
    new_c = st.session_state.get('add_c_bot', 0.0)
    clean_symbol = raw_sym.strip().upper().replace(".TW", "")
    if clean_symbol and new_name:
        final_symbol = f"{clean_symbol}.TW" 
        st.session_state.my_data['etfs'].append({
            "symbol": final_symbol, "name": new_name, "holdings": new_h, "cost": new_c, "pledged_shares": 0.0
        })
        save_to_json(st.session_state.my_data)
        st.session_state.add_sym_bot, st.session_state.add_name_bot, st.session_state.add_h_bot, st.session_state.add_c_bot = "", "", 0.0, 0.0

# 初始化按鈕狀態
for key in ['show_us', 'show_tw', 'show_calendar', 'show_div_db', 'show_tech', 'show_holdings', 'show_constituents', 'show_pledge']:
    if key not in st.session_state: st.session_state[key] = False

def toggle_us(): st.session_state.show_us = not st.session_state.show_us
def toggle_tw(): st.session_state.show_tw = not st.session_state.show_tw
def toggle_calendar(): st.session_state.show_calendar = not st.session_state.show_calendar
def toggle_div_db(): st.session_state.show_div_db = not st.session_state.show_div_db
def toggle_tech(): st.session_state.show_tech = not st.session_state.show_tech
def toggle_holdings(): st.session_state.show_holdings = not st.session_state.show_holdings
def toggle_constituents(): st.session_state.show_constituents = not st.session_state.show_constituents
def toggle_pledge(): st.session_state.show_pledge = not st.session_state.show_pledge 

# --- 📈 抓取大盤指標 ---
@st.cache_data(ttl=60) 
def fetch_macro_data():
    tickers = {
        "us": {"道瓊工業": "^DJI", "那斯達克": "^IXIC", "費半": "^SOX"},
        "tw": {"台股加權": "^TWII", "台積電": "2330.TW"}
    }
    res = {"us": {}, "tw": {}}
    for region, t_dict in tickers.items():
        for name, symbol in t_dict.items():
            try:
                tk = yf.Ticker(symbol)
                hist = tk.history(period="5d")
                if len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]; prev = hist['Close'].iloc[-2]
                    res[region][name] = {"price": curr, "diff": curr - prev, "pct": ((curr - prev)/prev)*100, "date": hist.index[-1].strftime("%m/%d")}
            except: pass
    return res

def render_macro_cards(data_dict, region_prefix):
    cols = st.columns(3)
    idx = 0
    for name, data in data_dict.items():
        color_hex = "#e74c3c" if data['diff'] >= 0 else "#2ecc71" 
        sign = "+" if data['diff'] >= 0 else ""
        html = f"""
        <div style="border:1px solid #e0e0e0; border-radius:8px; border-left:6px solid {color_hex}; padding:15px; margin-bottom:15px; background:#fff;">
            <div style="color:{color_hex}; font-size:15px; font-weight:bold; margin-bottom:10px;">{name}</div>
            <div style="font-size:24px; font-weight:900;">{data['price']:,.2f}</div>
            <div style="font-size:14px; font-weight:bold; color:{color_hex};">{sign}{data['diff']:,.2f} ({sign}{data['pct']:.2f}%)</div>
        </div>
        """
        cols[idx % 3].markdown(html, unsafe_allow_html=True)
        idx += 1

# --- 4. 核心數據計算 (加入均線判斷) ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(etf_list):
    if not etf_list: return pd.DataFrame(), pd.DataFrame(), 0, 0, 0, 0, {i: {"amount": 0, "sources": []} for i in range(1, 13)}
    results, tech_results = [], []
    total_mkt, total_cost, total_div, total_today_pnl = 0, 0, 0, 0
    monthly_calendar = {i: {"amount": 0, "sources": []} for i in range(1, 13)} 
    today = datetime.today()

    for item in etf_list:
        try:
            tk = yf.Ticker(item['symbol'])
            hist = tk.history(period='3mo') # 為了算月線，拉三個月資料
            if hist.empty: continue
            
            curr_p = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else curr_p
            
            # 計算 20 日均線 (月線)
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else curr_p
            trend_str = "📈 多頭 (站上月線)" if curr_p >= ma20 else "📉 空頭 (跌破月線)"

            shares = item['holdings'] * 1000
            mkt_val = shares * curr_p
            cost_val = shares * item['cost']
            
            is_etf = item['symbol'].startswith('00')
            tax_rate = 0.001 if is_etf else 0.003
            profit = mkt_val - cost_val - (mkt_val * (tax_rate + 0.001425))
            roi = (profit / cost_val * 100) if cost_val != 0 else 0
            
            today_profit = shares * (curr_p - prev_close)
            total_today_pnl += today_profit
            total_mkt += mkt_val; total_cost += cost_val
            
            cfg = DIVIDEND_DB.get(item['symbol'], {"v": 0, "d": "-", "p": "-"})
            div_amount = cfg['v']
            if div_amount > 0 and len(DIVIDEND_SCHEDULE.get(item['symbol'], [])) > 0:
                monthly_calendar[1]["amount"] += (shares * div_amount) # 簡化範例

            results.append({
                "代號": item['symbol'], "名稱": item['name'], "現價": curr_p, "均價": item['cost'],
                "張數": item['holdings'], "市值": mkt_val, "損益": profit, "報酬率": roi,
                "預估發放日": cfg['p']
            })
            
            tech_results.append({
                "ETF 名稱": item['name'], 
                "現價": round(curr_p, 2),
                "均價": item['cost'],
                "月線(20日)": round(ma20, 2),
                "長線趨勢": trend_str,
                "總損益": f"{profit:,.0f}"
            })
        except Exception: continue
        
    return pd.DataFrame(results), pd.DataFrame(tech_results), total_mkt, total_cost, total_div, total_today_pnl, monthly_calendar

df, df_tech, g_mkt, g_cost, g_div, g_today_pnl, monthly_calendar = fetch_data(st.session_state.my_data['etfs'])
macro_data = fetch_macro_data()

# --- 5. 介面呈現 ---
st.title("🛡️ 價值投資戰情室 (靜態版)")
st.caption(f"最後檢視時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

c1, c2, c3 = st.columns(3)
c1.metric("股票總市值", f"${g_mkt:,.0f}")
c2.metric("投資總成本", f"${g_cost:,.0f}")
total_net_profit = df['損益'].sum() if not df.empty else 0
c3.metric("累積預估淨損益", f"${total_net_profit:,.0f}")
st.write("---") 

cols_btn_r1 = st.columns(3)
cols_btn_r2 = st.columns(3)

b1_lbl = "🔽 收起美股" if st.session_state.show_us else "🌏 展開美股"
b2_lbl = "🔽 收起台股" if st.session_state.show_tw else "🇹🇼 展開台股"
b5_lbl = "🔽 收起股價趨勢監控" if st.session_state.show_tech else "📡 展開股價趨勢監控"
b6_lbl = "🔽 收起持股明細" if st.session_state.show_holdings else "📊 展開持股明細"

with cols_btn_r1[0]: st.button(b1_lbl, on_click=toggle_us, use_container_width=True)
with cols_btn_r1[1]: st.button(b2_lbl, on_click=toggle_tw, use_container_width=True)
with cols_btn_r2[0]: st.button(b5_lbl, on_click=toggle_tech, use_container_width=True)
with cols_btn_r2[1]: st.button(b6_lbl, on_click=toggle_holdings, use_container_width=True)
st.write("---")

if st.session_state.show_us and "us" in macro_data: render_macro_cards(macro_data["us"], "us")
if st.session_state.show_tw and "tw" in macro_data: render_macro_cards(macro_data["tw"], "tw")

# --- 📡 展開股價趨勢監控 (新增長線判斷) ---
if st.session_state.show_tech:
    if not df.empty:
        st.markdown("#### 📡 庫存趨勢監控 (重視長線)")
        st.caption("提示：只要長線趨勢顯示『多頭』，請忽略每日微小波動，安心持有。")
        st.dataframe(df_tech, use_container_width=True, hide_index=True)
    st.write("---")

# --- 📊 展開持股明細 ---
if st.session_state.show_holdings:
    if not df.empty:
        st.markdown("#### 📊 持股動態明細")
        for idx, item in enumerate(st.session_state.my_data['etfs']):
            row = df[df['代號'] == item['symbol']].iloc[0]
            with st.expander(f
