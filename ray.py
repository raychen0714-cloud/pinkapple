import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="戰情室", layout="wide")

# --- 💾 初始化 Session State 記憶體 ---
# 記憶你的總領配息金額
if 'total_div' not in st.session_state:
    st.session_state.total_div = 0.0

# 記憶你手動更新的配息資料
if 'custom_div_map' not in st.session_state:
    st.session_state.custom_div_map = {
        "00919.TW": "1.0元 (請至左側手動更新日期)",
        "00918.TW": "1.26元 (請至左側手動更新日期)",
        "0056.TW": "1.0元 (2026-04-23)" 
    }

# --- 💰 存股配息金庫 (全新頂部 UI) ---
st.markdown("### 💰 存股配息金庫")
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📥 紀錄本月配息入帳")
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        month_input = st.number_input("月份", min_value=1, max_value=12, value=6, step=1)
    with c2:
        amount_input = st.number_input("入帳金額 (元)", min_value=0, value=0, step=100)
    with c3:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕ 加入總額", use_container_width=True):
            st.session_state.total_div += amount_input
            st.rerun()

with col_right:
    st.markdown("#### 🏆 總領配息累計")
    # 使用藍色大字體凸顯成就感
    st.markdown(f"<h1 style='color: #1e3c72; font-weight: 900; font-size: 48px;'>${st.session_state.total_div:,.0f}</h1>", unsafe_allow_html=True)

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
        "3034.TW": "聯詠", "2379.TW": "瑞昱", "2344.TW": "華邦電", "2408.TW": "南亞科", 
        "3443.TW": "創意", "3661.TW": "世芯-KY", "6415.TW": "矽力-KY", "8046.TW": "南電", 
        "3189.TW": "景碩", "3037.TW": "欣興", "5347.TW": "世界先進", "6239.TW": "力成",
        "2338.TW": "光罩", "3583.TW": "辛耘", "3131.TW": "弘塑", "6147.TW": "頎邦",
        "3227.TW": "原相", "2449.TW": "京元電子"
    },
    "光電與面板": {
        "3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶", "3008.TW": "大立光", 
        "3406.TW": "玉晶光", "3714.TW": "富采", "2498.TW": "宏達電", "6209.TW": "今國光"
    }
}

ETF_UNIVERSE = {
    "高股息": {
        "00878.TW": "國泰永續高股息", "0056.TW": "元大高股息", "00919.TW": "群益精選高息", 
        "00929.TW": "復華台灣科技優息", "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息30", 
        "00900.TW": "富邦特選高股息30", "00918.TW": "大華優利高填息30"
    },
    "半導體與科技": {
        "00927.TW": "群益半導體收益", "00881.TW": "國泰台灣5G+", "00891.TW": "中信關鍵半導體",
        "00892.TW": "富邦台灣半導體", "00935.TW": "野村臺灣新科技50"
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

max_price = st.sidebar.number_input("3. 設定最高價位 (元)", value=100, step=10)

st.sidebar.markdown("---")
manual_tickers_str = st.sidebar.text_input(
    "🔍 4. 手動新增觀察標的", 
    value="878, 919, 918, 0056, 927, 0052, 2409, 6116", 
    placeholder="如: 878, 56, 3131"
)

# 🔥 全新：手動強制更新配息區塊
st.sidebar.markdown("---")
st.sidebar.markdown("### ✏️ 5. 手動更新最新配息")
st.sidebar.caption("Yahoo 沒更新的，我們自己來！")
update_ticker = st.sidebar.text_input("輸入代號 (如 00919)", key="up_t")
update_amt = st.sidebar.text_input("配息金額 (如 1.0)", key="up_a")
update_date = st.sidebar.text_input("除息日期 (如 2026-06-15)", key="up_d")

if st.sidebar.button("💾 強制更新配息資料", use_container_width=True):
    if update_ticker and update_amt and update_date:
        t_key = f"{update_ticker}.TW" if not update_ticker.endswith(".TW") else update_ticker
        # 將最新的金額與日期寫入你的專屬記憶體
        st.session_state.custom_div_map[t_key] = f"{update_amt}元 ({update_date})"
        st.rerun()

# --- 🧠 3. 核心運算引擎 ---
# 注意：這裡把 custom_divs 傳進來，這樣你只要一更新，系統就會重算
@st.cache_data(ttl=30) 
def fetch_and_analyze(categories, universe_dict, price_limit, current_type, manual_input, custom_divs):
    tickers_to_fetch = {}
    
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat].copy())
        
    manual_symbols = []
    if manual_input:
        clean_input = manual_input.replace("，", ",").replace("、", ",").replace(" ", ",")
        raw_tickers = [t.strip().upper() for t in clean_input.split(",") if t.strip()]
        
        for t in raw_tickers:
            if len(t) <= 3 and t.isdigit():
                t = f"00{t}"
            elif len(t) == 4 and (t.endswith('R') or t.endswith('L')) and t[0] != '0':
                t = f"00{t}"
                
            t_symbol = f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t
            
            display_name = "自選標的"
            for cat_key, stocks in STOCK_UNIVERSE.items():
                if t_symbol in stocks: display_name = stocks[t_symbol]
            for cat_key, etfs in ETF_UNIVERSE.items():
                if t_symbol in etfs: display_name = etfs[t_symbol]
                
            tickers_to_fetch[t_symbol] = display_name
            manual_symbols.append(t_symbol)
    
    if not tickers_to_fetch:
        return pd.DataFrame()

    results = [] 
    
    for ticker, name in tickers_to_fetch.items():
        try:
            is_manual = (ticker in manual_symbols)
            tk = yf.Ticker(ticker)
            
            if name == "自選標的":
                if ticker in CUSTOM_NAME_MAP:
                    name = CUSTOM_NAME_MAP[ticker]
                else:
                    try:
                        real_name = tk.info.get("shortName")
                        if real_name:
                            name = real_name
                    except:
                        pass

            div_info = "-"
            if is_manual:
                # 🔥 直接去你的「專屬記憶體」裡面拿你剛剛設定的配息與日期
                if ticker in custom_divs:
                    div_info = custom_divs[ticker]
                else:
                    try:
                        divs = tk.dividends
                        if not divs.empty:
                            last_div = round(float(divs.iloc[-1]), 3)
                            last_date = divs.index[-1].strftime("%Y-%m-%d")
                            div_info = f"{last_div}元 ({last_date})"
                    except:
                        pass

            hist = tk.history(period="6mo", auto_adjust=False)
            
            if hist.empty and is_manual and ticker.endswith(".TW"):
                ticker_two = ticker.replace(".TW", ".TWO")
                tk = yf.Ticker(ticker_two)
                hist = tk.history(period="6mo", auto_adjust=False)
                if not hist.empty:
                    ticker = ticker_two 
                    
            if hist.empty: continue
            
            hist = hist.replace([np.inf, -np.inf], np.nan).dropna(subset=['Close', 'Volume'])
            
            if len(hist) < 10 and is_manual: continue
            elif len(hist) < 60 and not is_manual: continue
            
            try:
                close_px = float(tk.fast_info.last_price)
                if np.isnan(close_px) or close_px <= 0:
                    close_px = float(hist['Close'].iloc[-1])
            except:
                close_px = float(hist['Close'].iloc[-1])
                
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
            
            if ma60 > 0 and close_px > ma5 > ma20 > ma60:
                trend_status = "🔥 多頭排列 (強勢)" 
            elif ma60 > 0 and close_px < ma5 < ma20 < ma60:
                trend_status = "🧊 空頭排列 (極弱)" 
            elif ma60 > 0 and close_px > ma60:
                trend_status = "🔼 站上季線 (波段看多)" 
            elif ma60 == 0:
                trend_status = "📈 數據不足 (新股觀察)"
            else:
                trend_status = "🔽 跌破季線 (波段防守)" 

            if current_type == "ETF" or (is_manual and ticker.replace(".TW","").replace(".TWO","").startswith("00")):
                if trend_status in ["🔽 跌破季線 (波段防守)", "🧊 空頭排列 (極弱)"] and bias < -10:
                    note = "💎 跌深超賣！殖利率浮現，絕佳抄底撿便宜時機！"
                elif trend_status in ["🔥 多頭排列 (強勢)", "🔼 站上季線 (波段看多)"]:
                    note = "🟢 趨勢向上，適合分批布局"
                else:
                    note = "⚪ 進入整理，建議保持觀望"
            else:
                if vol_surge and px_up:
                    note = "🐋 疑似大戶進場，強勢表態可跟進！"
                elif vol_surge and not px_up:
                    note = "🚨 疑似大戶倒貨，嚴格控管風險！"
                elif px_up and trend_status in ["🔥 多頭排列 (強勢)", "🔼 站上季線 (波段看多)"]:
                    note = "🟢 趨勢強勢，可積極關注布局"
                elif px_up:
                    note = "🟡 溫和上漲，可續抱，不宜追高"
                else:
                    note = "⚪ 量縮回檔，觀察支撐是否有效"
                
            if bias > 20:
                note = "🔥 乖離率過高，短線極度過熱，請留意獲利了結"
                
            results.append({
                "is_manual": is_manual,
                "代號": ticker.replace(".TW", "").replace(".TWO",""), 
                "名稱": name,
                "現價": round(close_px, 2), 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "🤖 系統建議": note,
                "💰 最新配息": div_info
            })
        except:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["is_manual", "成交量(張)"], ascending=[False, False])
        df = df.drop(columns=["is_manual"])
    return df 

# --- 📊 4. 畫面渲染 ---
st.subheader(f"🔍 {target_type} 觀察雷達 (最高價 {max_price} 元以下)")

with st.spinner("真實證券報價與配息資料同步中..."):
    # 將 session_state 裡的手動配息紀錄傳進去運算
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price, target_type, manual_tickers_str, st.session_state.custom_div_map)

if not final_data.empty:
    final_data['標的'] = final_data['代號'].astype(str) + " " + final_data['名稱']
    
    display_df = final_data[['標的', '🤖 系統建議', '現價', '成交量(張)', '趨勢格局', '💰 最新配息']]
    
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=False, 
        column_config={
            "標的": st.column_config.TextColumn("標的"),
            "🤖 系統建議": st.column_config.TextColumn("🤖 系統建議"), 
            "現價": st.column_config.NumberColumn("現價"),
            "成交量(張)": st.column_config.NumberColumn("成交量"),
            "趨勢格局": st.column_config.TextColumn("趨勢格局"),
            "💰 最新配息": st.column_config.TextColumn("💰 最新配息")
        }
    )
else:
    st.info("請確認手動輸入代號後是否已按下鍵盤上的『確認/Enter』鍵，或放寬篩選產業。")
