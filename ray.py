import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="戰情室", layout="wide")

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
    },
    "航運": {
        "2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海", "2610.TW": "華航", 
        "2618.TW": "長榮航", "2606.TW": "裕民", "2637.TW": "慧洋-KY", "2614.TW": "東森"
    },
    "電子與電腦周邊": {
        "2317.TW": "鴻海", "2382.TW": "廣達", "3231.TW": "緯創", "2356.TW": "英業達", 
        "2324.TW": "仁寶", "2301.TW": "光寶科", "2357.TW": "華碩", "2353.TW": "宏碁"
    },
    "金融": {
        "2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金", "2886.TW": "兆豐金",
        "2884.TW": "玉山金", "2892.TW": "第一金", "2880.TW": "華南金", "2885.TW": "元大金"
    },
    "重電與綠能": {
        "1519.TW": "華城", "1503.TW": "士電", "1513.TW": "中興電", "1514.TW": "亞力",
        "1609.TW": "大亞", "3708.TW": "上緯投控", "6806.TW": "森崴能源"
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
    },
    "大盤與槓桿": {
        "006208.TW": "富邦台50", 
        "00631L.TW": "元大台灣50正2", "00632R.TW": "元大台灣50反1", "00670L.TW": "富邦NASDAQ正2"
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
# 手動輸入框
manual_tickers_str = st.sidebar.text_input("🔍 4. 手動新增觀察標的", placeholder="如: 878, 56, 2330")

# --- 🧠 3. 核心運算引擎 ---
@st.cache_data(ttl=30) 
def fetch_and_analyze(categories, universe_dict, price_limit, current_type, manual_input):
    tickers_to_fetch = {}
    
    # 先載入勾選的預設標的
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat].copy())
        
    # 建立手動名單與智慧補零機制
    manual_symbols = []
    if manual_input:
        raw_tickers = [t.strip().upper() for t in manual_input.split(",") if t.strip()]
        for t in raw_tickers:
            # 自動補零
            if len(t) <= 3 and t.isdigit():
                t = f"00{t}"
            elif len(t) == 4 and (t.endswith('R') or t.endswith('L')) and t[0] != '0':
                t = f"00{t}"
                
            t_symbol = f"{t}.TW" if not (t.endswith(".TW") or t.endswith(".TWO")) else t
            
            # 檢查預設清單有沒有名稱，沒有就用「自選標的」
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
            
            # 抓取歷史半年數據
            hist = tk.history(period="6mo", auto_adjust=False)
            if hist.empty: continue
            
            # 徹底清洗假日造成的空值
            hist = hist.replace([np.inf, -np.inf], np.nan).dropna(subset=['Close', 'Volume'])
            if len(hist) < 60: continue
            
            # 優先獲取真實收盤價
            try:
                close_px = float(tk.fast_info.last_price)
                if np.isnan(close_px) or close_px <= 0:
                    close_px = float(hist['Close'].iloc[-1])
            except:
                close_px = float(hist['Close'].iloc[-1])
                
            # 🔥 特權 1：手動輸入標的無視最高價格限制
            if not is_manual and close_px > price_limit: continue
            
            prev_px = float(hist['Close'].iloc[-2])
            vol = float(hist['Volume'].iloc[-1]) / 1000  
            
            # 🔥 特權 2：手動輸入標的無視量小過濾限制
            if not is_manual and vol < 1000 and current_type == "個股": continue 

            vol_5ma = float(hist['Volume'].tail(5).mean()) / 1000
            ma5 = float(hist['Close'].tail(5).mean())    
            ma20 = float(hist['Close'].tail(20).mean())  
            ma60 = float(hist['Close'].tail(60).mean())  
            
            bias = ((close_px - ma20) / ma20) * 100  
            px_up = close_px > prev_px               
            
            vol_surge = (vol_5ma > 0 and (vol / vol_5ma) >= 2.0)
            
            if close_px > ma5 > ma20 > ma60:
                trend_status = "🔥 多頭排列 (強勢)" 
            elif close_px < ma5 < ma20 < ma60:
                trend_status = "🧊 空頭排列 (極弱)" 
            elif close_px > ma60:
                trend_status = "🔼 站上季線 (波段看多)" 
            else:
                trend_status = "🔽 跌破季線 (波段防守)" 

            # 決策引擎 (手動輸入若為00開頭自動走精確存股策略)
            if current_type == "ETF" or (is_manual and ticker.replace(".TW","").startswith("00")):
                if trend_status in ["🔥 多頭排列 (強勢)", "🔼 站上季線 (波段看多)"]:
                    status = "趨勢向上"
                    note = "🟢 趨勢向上，適合分批布局"
                else:
                    status = "整理中"
                    note = "⚪ 進入整理，建議保持觀望"
            else:
                if vol_surge and px_up:
                    status = "💥 爆量起漲"
                    note = "🐋 疑似大戶進場，強勢表態可跟進！"
                elif vol_surge and not px_up:
                    status = "⚠️ 爆量下殺"
                    note = "🚨 疑似大戶倒貨，嚴格控管風險！"
                elif px_up and trend_status in ["🔥 多頭排列 (強勢)", "🔼 站上季線 (波段看多)"]:
                    status = "強勢表態"
                    note = "🟢 趨勢強勢，可積極關注布局"
                elif px_up:
                    status = "緩步墊高"
                    note = "🟡 溫和上漲，可續抱，不宜追高"
                else:
                    status = "整理中"
                    note = "⚪ 量縮回檔，觀察支撐是否有效"
                
            if bias > 20:
                note = "🔥 乖離率過高，短線過熱留意停利"
                
            results.append({
                "代號": ticker.replace(".TW", "").replace(".TWO",""), 
                "名稱": name,
                "現價": round(close_px, 2), 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "🤖 系統建議": note
            })
        except:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="成交量(張)", ascending=False)
    return df 

# --- 📊 4. 畫面渲染 ---
st.subheader(f"🔍 {target_type} 觀察雷達 (最高價 {max_price} 元以下)")

with st.spinner("真實證券報價同步中..."):
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price, target_type, manual_tickers_str)

if not final_data.empty:
    final_data['標的'] = final_data['代號'].astype(str) + " " + final_data['名稱']
    display_df = final_data[['標的', '🤖 系統建議', '現價', '成交量(張)', '趨勢格局']]
    
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=False, 
        column_config={
            "標的": st.column_config.TextColumn("標的"),
            "🤖 系統建議": st.column_config.TextColumn("🤖 系統建議"), 
            "現價": st.column_config.NumberColumn("現價"),
            "成交量(張)": st.column_config.NumberColumn("成交量"),
            "趨勢格局": st.column_config.TextColumn("趨勢格局")
        }
    )
else:
    st.info("請確認手動輸入代號後是否已按下鍵盤上的『確認/Enter』鍵，或放寬篩選產業。")
