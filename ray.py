import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET

# --- ⚙️ 頁面設定與資料載入 ---
st.set_page_config(page_title="PRO 級存股戰情室", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "user_data.json")

def load_data():
    default_data = {
        "total_div": 0.0, 
        "held_stocks": ["00878.TW", "0056.TW", "00927.TW", "00905.TW", "00919.TW", "00918.TW"],
        "manual_tickers": "878, 919, 918, 0056, 927, 0052, 2409, 6116, 3481, 00905, 2330, 2303, 2454, 00403A, 2327, 3711, 6742, 6770"
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**default_data, **data}
        except: return default_data
    return default_data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'app_data' not in st.session_state:
    st.session_state.app_data = load_data()

# --- 📰 新聞輿情引擎 ---
@st.cache_data(ttl=600)
def fetch_news_and_sentiment(stock_name):
    try:
        query = urllib.parse.quote(f"{stock_name} 股市")
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        res = requests.get(url, timeout=3)
        root = ET.fromstring(res.text)
        items = root.findall('.//item')
        if not items: return "➖ 中性", "無近期新聞"
        
        title = items[0].find('title').text.split(" - ")[0]
        text = " ".join([item.find('title').text for item in items[:3]])
        pos = ["大漲", "創高", "買超", "利多", "上修", "受惠", "營收增", "突破", "強勁", "飆"]
        neg = ["跌", "賣超", "利空", "下修", "衰退", "砍單", "外資逃", "疲弱", "降評", "重挫"]
        
        p = sum(1 for k in pos if k in text)
        n = sum(1 for k in neg if k in text)
        
        if p > n: sentiment = "🔥 利多"
        elif n > p: sentiment = "🚨 利空"
        else: sentiment = "➖ 中性"
        return sentiment, title
    except: return "➖ 中性", "新聞讀取中..."

# --- 🧠 核心處理引擎 (強化矩陣對齊) ---
@st.cache_data(ttl=60)
def fetch_and_analyze(manual_input):
    clean_input = manual_input.replace("，", ",").replace(" ", ",")
    tickers = [t.strip().upper() for t in clean_input.split(",") if t.strip()]
    processed_tickers = []
    for t in tickers:
        if len(t) <= 3 and t.isdigit(): t = f"00{t}"
        processed_tickers.append(f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t)

    all_hist_pct = {}
    results = []
    
    for ticker in processed_tickers:
        try:
            tk = yf.Ticker(ticker)
            # 強制拉取近一個月數據，並確保索引是對齊的日期
            hist = tk.history(period="1mo")
            if hist.empty: continue
            
            hist.index = hist.index.normalize()
            pct_change = hist['Close'].pct_change() * 100
            
            # 使用 name 存入字典
            name = tk.info.get('shortName', ticker)
            all_hist_pct[f"{ticker.split('.')[0]} {name}"] = pct_change
            
            # 準備列表資訊
            latest_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            change_pct = ((latest_price - prev_price) / prev_price) * 100
            
            sentiment, title = fetch_news_and_sentiment(name)
            
            results.append({
                "代號": ticker.split('.')[0],
                "名稱": name,
                "現價": round(latest_price, 2),
                "漲跌幅": f"{change_pct:+.2f}%",
                "🤖 消息面": sentiment,
                "📰 最新新聞": title
            })
        except: continue

    # 🚀 關鍵：將所有股票的漲跌幅合併，未交易日強制補零
    df_matrix = pd.DataFrame(all_hist_pct)
    df_matrix = df_matrix.fillna(0) 
    
    # 將日期格式化為字串，方便顯示
    df_matrix.index = df_matrix.index.strftime('%m/%d')
    
    return pd.DataFrame(results), df_matrix.T # 轉置讓股票在左側，日期在上方

# --- UI 渲染 ---
st.subheader("📊 存股戰情室")
manual_tickers_str = st.sidebar.text_input("輸入代號", value=st.session_state.app_data["manual_tickers"])
df_list, df_matrix = fetch_and_analyze(manual_tickers_str)

if not df_list.empty:
    st.dataframe(df_list, use_container_width=True)
    
    st.markdown("### 📉 每日漲跌幅矩陣 (已強制補零對齊)")
    # 這裡顯示矩陣，給予最大寬度
    st.dataframe(df_matrix.style.background_gradient(cmap="RdYlGn", axis=None), use_container_width=True)
else:
    st.warning("請在左側輸入正確代號並稍等片刻...")
