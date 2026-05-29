import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="ETF 投資戰情室", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    [data-testid="stMetricDelta"] svg { fill: red; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; }
    .auto-refresh-box { background-color: #f0f7ff; border: 1px solid #cce5ff; border-radius: 8px; padding: 15px; text-align: center; }
    div.stButton > button { font-weight: bold; border-radius: 8px; }
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
    "00878.TW": {"v": 0.66, "d": "2026-05-19", "p": "2026-06-16"},
    "0050.TW": {"v": 1.00, "d": "2026-01-16", "p": "2026-02-20"}
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except: 
            pass
    
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
    if 'pledged_shares' not in etf: 
        etf['pledged_shares'] = 0.0
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
    clean_symbol = raw_sym.strip().upper().replace
