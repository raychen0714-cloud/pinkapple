import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 級存股戰情室", layout="wide")

# --- 💾 永久記憶系統 (防雲端失憶機制) ---
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
                saved_data = json.load(f)
                for key, value in default_data.items():
                    if key not in saved_data:
                        saved_data[key] = value
                return saved_data
        except: 
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except: pass

if 'app_data' not in st.session_state:
    st.session_state.app_data = load_data()

# --- 📘 字典區 ---
CUSTOM_NAME_MAP = {
    "2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "2317.TW": "鴻海",
    "2327.TW": "國巨", "3711.TW": "日月光投控", "6742.TW": "澤米", "6770.TW": "力積電",
    "4958.TW": "臻鼎-KY", "3037.TW": "欣興", "3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶",
    "00981A.TW": "瑤姊", "00631L.TW": "元大正2", "00685L.TW": "群益正2", "0052.TW": "富邦科技",
    "009816.TW": "凱基台灣TOP50", "0050.TW": "元大台灣50", "0056.TW": "元大高股息",
    "00878.TW": "國泰永續高股息", "00919.TW": "群益精選高息", "00929.TW": "復華台灣科技優息",
    "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息", "00918.TW": "大華優利高填息",
    "00927.TW": "群益半導體收益", "00939.TW": "統一台灣高息動能", "00940.TW": "元大台灣價值高息",
    "00905.TW": "FT台灣Smart", "00403A.TW": "主動統一升級50"
}

# --- ⚙️ Pandas 顯色引擎相容包 ---
def safe_style_map(styler, color_func, subset=None):
    try:
        return styler.map(color_func, subset=subset)
    except AttributeError:
        return styler.applymap(color_func, subset=subset)

# --- 📰 輿情引擎 ---
@st.cache_data(ttl=600)
def fetch_news_and_sentiment(stock_name):
    try:
        query = urllib.parse.quote(f"{stock_name} 股市")
        url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        res = requests.get(url, timeout=4)
        root = ET.fromstring(res.text)
        items = root.findall('.//item')
        if not items: return "➖ 中性", "近期無重大新聞"
            
        latest_title = items[0].find('title').text.split(" - ")[0] 
        combined_text = " ".join([item.find('title').text for item in items[:2]])
        
        pos_kw = ["大漲", "創高", "買超", "看好", "利多", "上修", "受惠", "營收增", "突破", "強勁", "飆", "高息", "亮眼", "漲停"]
        neg_kw = ["跌", "賣超", "看壞", "利空", "下修", "衰退", "砍單", "外資逃", "探底", "疲弱", "保守", "降評", "重挫", "跌停"]
        
        p_score = sum(1 for k in pos_kw if k in combined_text)
        n_score = sum(1 for k in neg_kw if k in combined_text)
        
        if p_score > n_score: sentiment = "🔥 利多"
        elif n_score > p_score: sentiment = "🚨 利空"
        else: sentiment = "➖ 中性"
        return sentiment, latest_title
    except: return "➖ 中性", "新聞讀取中..."

# --- ⚡ 即時報價引擎 ---
@st.cache_data(ttl=5)
def fetch_twse_realtime(tickers):
    ex_ch_list = []
    for t in tickers:
        code = t.split('.')[0]
        if '.TW' in t and len(code) >= 4: ex_ch_list.append(f"tse_{code}.tw")
        elif '.TWO' in t and len(code) >= 4: ex_ch_list.append(f"otc_{code}.tw")

    if not ex_ch_list: return {}
    results = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        session = requests.Session()
        session.get("https://mis.twse.com.tw/stock/index.jsp", headers=headers, timeout=5)
        for i in range(0, len(ex_ch_list), 15):
            chunk = ex_ch_list[i:i + 15]
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={'|'.join(chunk)}&json=1&delay=0"
            res = session.get(url, headers=headers, timeout=5)
            data = res.json()
            for item in data.get('msgArray', []):
                try:
                    code = item.get('c')
                    ex = item.get('ex')
                    z_val = str(item.get('z', '-')).replace(',', '')
                    y_val = str(item.get('y', '0')).replace(',', '')
                    
                    if z_val != '-': price = float(z_val)
                    else:
                        b_val = str(item.get('b', '')).split('_')[0].replace(',', '')
                        if b_val and b_val != '-': price = float(b_val)
                        else: price = float(y_val)
                        
                    prev_close = float(y_val)
                    vol = int(item.get('v', 0))
                    original_ticker = f"{code}.TW" if ex == 'tse' else f"{code}.TWO"
                    if price > 0: results[original_ticker] = {"price": price, "prev_close": prev_close, "vol": vol}
                except: continue
        return results
    except: return results

# --- 💰 存股金庫 UI ---
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
    with st.expander("🛠️ 手動校正總額"):
        correct_val = st.number_input("輸入正確總金額", value=int(st.session_state.app_data['total_div']), step=1000)
        if st.button("💾 覆寫總額", use_container_width=True):
            st.session_state.app_data["total_div"] = float(correct_val)
            save_data(st.session_state.app_data)
            st.rerun()
st.markdown("---")

st.sidebar.header("🎛️ 觀察清單控制台")
saved_tickers = st.session_state.app_data.get("manual_tickers")
manual_tickers_str = st.sidebar.text_input("🔍 手動輸入股票/ETF代號 (用逗號隔開)", value=saved_tickers)

if manual_tickers_str != saved_tickers:
    st.session_state.app_data["manual_tickers"] = manual_tickers_str
    save_data(st.session_state.app_data)
    st.rerun()

# --- 🧠 核心處理引擎 ---
@st.cache_data(ttl=60)  
def fetch_and_analyze(manual_input):
    tickers_to_fetch = {}
    if manual_input:
        clean_input = manual_input.replace("，", ",").replace("、", ",").replace(" ", ",")
        for t in [t.strip().upper() for t in clean_input.split(",") if t.strip()]:
            if len(t) <= 3 and t.isdigit(): t = f"00{t}"
            t_symbol = f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t
            name = CUSTOM_NAME_MAP.get(t_symbol, "自選標的")
            tickers_to_fetch[t_symbol] = name
    
    if not tickers_to_fetch: return pd.DataFrame(), pd.DataFrame()
    
    realtime_data = fetch_twse_realtime(list(tickers_to_fetch.keys()))
    results = [] 
    all_hist_pct = {} 
    
    for ticker, name in tickers_to_fetch.items():
        code_only = ticker.split('.')[0]
        display_name = f"{code_only} {name}"
        try:
            tk = yf.Ticker(ticker)
            if name == "自選標的":
                try: 
                    real_name = tk.info.get("shortName")
                    if real_name: name = real_name[:8] + ".." if len(real_name) > 8 else real_name
                except: pass

            hist = tk.history(period="1mo", auto_adjust=False)
            if hist.empty and ticker.endswith(".TW"):
                ticker_two = ticker.replace(".TW", ".TWO")
                tk = yf.Ticker(ticker_two)
                hist = tk.history(period="1mo", auto_adjust=False)
                if not hist.empty: ticker = ticker_two 
                    
            if hist.empty or len(hist) < 2: continue
            
            hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
            hist = hist.ffill()

            hist_pct = hist['Close'].pct_change() * 100
            hist_diff = hist['Close'].diff()
            
            valid_idx = hist_pct.dropna().index
            combined_series = pd.Series([f"{hist_pct[d]:.3f},{hist_diff[d]:.3f}" for d in valid_idx], index=valid_idx)
            all_hist_pct[display_name] = combined_series

            sentiment, latest_title = fetch_news_and_sentiment(name)
            rt_info = realtime_data.get(ticker)
            if rt_info and rt_info['prev_close'] > 0 and rt_info['price'] > 0:
                close_px = rt_info['price']
                prev_close = rt_info['prev_close']
                vol = rt_info['vol']
            else:
                close_px = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else close_px
                vol = float(hist['Volume'].iloc[-1]) / 1000
                
            price_change_abs = close_px - prev_close 
            price_change_pct = (price_change_abs / prev_close) * 100 if prev_close > 0 else 0
            
            if price_change_abs > 0: change_str = f"🔺 +{price_change_pct:.2f}% / +{price_change_abs:.2f}元"
            elif price_change_abs < 0: change_str = f"🔻 {price_change_pct:.2f}% / {price_change_abs:.2f}元"
            else: change_str = "➖ 0.00% / 0.00元"

            ma5 = float(hist['Close'].tail(5).mean())   
            ma20 = float(hist['Close'].tail(20).mean())  
            if close_px > ma5 and close_px > ma20: trend_status = "🔥 偏多" 
            elif close_px < ma5 and close_px < ma20: trend_status = "🧊 偏空" 
            else: trend_status = "➖ 整理" 

            results.append({
                "原始代號": ticker,  
                "代號": code_only, 
                "名稱": name,
                "現價": round(close_px, 2), 
                "📈 漲跌": change_str, 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,
                "消息面": sentiment,
                "📰 最新新聞": latest_title
            })
        except: continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["成交量(張)"], ascending=[False]).reset_index(drop=True)
        
    hist_df = pd.DataFrame(all_hist_pct)
    if not hist_df.empty:
        hist_df = hist_df.dropna(how='all')
        hist_df = hist_df.fillna("0.000,0.000")
        hist_df.index = hist_df.index.strftime('%m/%d')
        hist_matrix = hist_df.T 
    else:
        hist_matrix = pd.DataFrame()
        
    return df, hist_matrix

# ==========================================
# 【上方面板】即時觀察雷達
# ==========================================
st.subheader("🔍 PRO 觀察雷達 (即時報價 + 新聞輿情)")
col1, col2 = st.columns([8, 2])
with col2:
    if st.button("🔄 強制刷新報價與新聞", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("官方 MIS 連線中... 正在同步市場風向..."):
    final_data, history_matrix = fetch_and_analyze(manual_tickers_str)

if final_data.empty:
    st.warning("⚠️ 系統目前無法取得報價資料，請確認代號是否輸入正確。")
else:
    held_list = st.session_state.app_data.get("held_stocks", [])
    final_data['📌 持有'] = final_data['原始代號'].apply(lambda x: x in held_list)
    final_data['標的'] = final_data['代號'].astype(str) + " " + final_data['名稱']
    
    display_df = final_data[['📌 持有', '原始代號', '標的', '現價', '📈 漲跌', '成交量(張)', '趨勢格局', '消息面', '📰 最新新聞']]
    display_df = display_df.sort_values(by=["📌 持有", "成交量(張)"], ascending=[False, False]).reset_index(drop=True)
    
    def color_tw_stock(val):
        if isinstance(val, str):
            if '🔺' in val or '+' in val or '🔥' in val: return 'color: #ff4b4b; font-weight: bold;'
            elif '🔻' in val or '-' in val or '🚨' in val: return 'color: #09ab3b; font-weight: bold;'
        return ''

    styled_df = safe_style_map(display_df.style, color_tw_stock, subset=['📈 漲跌', '消息面'])
    dynamic_height = int(len(display_df) * 45) + 60
    
    edited_df = st.data_editor(
        styled_df, 
        key="portfolio_editor", 
        hide_index=True, 
        use_container_width=True,
        height=dynamic_height, 
        disabled=["標的", "現價", "📈 漲跌", "成交量(張)", "趨勢格局", "消息面", "📰 最新新聞"], 
        column_config={
            "📌 持有": st.column_config.CheckboxColumn("📌 持有", width=60),
            "原始代號": None, 
            "標的": st.column_config.TextColumn("標的", width=130), 
            "現價": st.column_config.NumberColumn("現價", format="$%.2f", width=70),
            "📈 漲跌": st.column_config.TextColumn("📈 漲跌", width=160), 
            "成交量(張)": st.column_config.NumberColumn("成交量", width=80),
            "趨勢格局": st.column_config.TextColumn("趨勢", width=90),
            "消息面": st.column_config.TextColumn("消息面", width=90),
            "📰 最新新聞": st.column_config.TextColumn("📰 最新新聞標題", width=300)
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

    if has_changes:
        st.session_state.app_data["held_stocks"] = current_held
        save_data(st.session_state.app_data)       
        st.rerun()

# ==========================================
# 【下方面板】歷史區間漲跌幅矩陣 (解決被切斷的問題)
# ==========================================
st.markdown("---")
st.subheader("📉 歷史漲跌幅追蹤矩陣 (自訂天數)")

col_slider, col_check = st.columns([3, 1])
with col_slider:
    lookback_days = st.slider("📅 設定要往前追蹤的交易天數", min_value=1, max_value=30, value=5, key="matrix_slider")
with col_check:
    st.markdown("<div style='margin-top: 35px;'></div>", unsafe_allow_html=True)
    only_show_held = st.checkbox("✅ 只顯示我持有的標的", value=True)

if not history_matrix.empty:
    if only_show_held and not final_data.empty:
        held_targets = final_data[final_data['📌 持有'] == True]['標的'].tolist()
        filtered_matrix = history_matrix[history_matrix.index.isin(held_targets)]
    else:
        filtered_matrix = history_matrix

    if filtered_matrix.empty:
        st.info("💡 您目前尚未勾選持有任何標的。請在上方表格勾選「📌 持有」，或取消右側「✅ 只顯示我持有的標的」以查看全部。")
    else:
        actual_cols = filtered_matrix.shape[1]
        slice_days = min(lookback_days, actual_cols)
        
        # 切片並倒序 (今天在最左邊)
        recent_history = filtered_matrix.iloc[:, -slice_days:]
        recent_history = recent_history.iloc[:, ::-1] 
        recent_history = recent_history.fillna("0.000,0.000") 
        
        # 🚀 格式化引擎：移除換行符號，改用「括號」放在同一排，徹底解決 Streamlit 斷字切頭切尾的問題！
        def format_matrix_value(val):
            if pd.isna(val) or val == "0.000,0.000": return "➖ 0.00% (0.00元)"
            try:
                pct_str, diff_str = val.split(',')
                pct, diff = float(pct_str), float(diff_str)
                if pct > 0: return f"🔺 +{pct:.2f}% (+{diff:.2f}元)"
                elif pct < 0: return f"🔻 {pct:.2f}% ({diff:.2f}元)"
                return "➖ 0.00% (0.00元)"
            except:
                return "➖ 0.00% (0.00元)"
            
        formatted_hist_df = recent_history.apply(lambda col: col.map(format_matrix_value))
        colored_hist = safe_style_map(formatted_hist_df.style, color_tw_stock)
        
        # 高度恢復正常設定
        matrix_height = int(len(formatted_hist_df) * 40) + 50
        st.dataframe(colored_hist, use_container_width=True, height=matrix_height)
else:
    st.info("💡 歷史資料正在對齊同步中，若未出現請點擊上方強制刷新按鈕。")
