import streamlit as st
import yfinance as yf
import pandas as pd

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 戰情室", layout="wide")
st.title("🚀 PRO 級自動化決策戰情室")
st.markdown("---")

# --- 📂 1. 定義標的池 (擴充版水庫 - 包含 6147 頎邦與熱門 ETF) ---
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

# --- 🧠 3. 核心運算引擎 (情緒穩定版雙引擎) ---
@st.cache_data(ttl=300) 
def fetch_and_analyze(categories, universe_dict, price_limit, current_type):
    
    tickers_to_fetch = {}
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat])
    
    if not tickers_to_fetch:
        return pd.DataFrame()

    results = [] 
    
    for ticker, name in tickers_to_fetch.items():
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="6mo")
            
            if hist.empty or len(hist) < 60: continue
            
            close_px = hist['Close'].iloc[-1]
            if close_px > price_limit: continue
            
            prev_px = hist['Close'].iloc[-2]
            vol = hist['Volume'].iloc[-1] / 1000  
            
            if vol < 1000 and current_type == "個股": continue 

            vol_5ma = (hist['Volume'].tail(5).mean()) / 1000
            ma5 = hist['Close'].tail(5).mean()    
            ma20 = hist['Close'].tail(20).mean()  
            ma60 = hist['Close'].tail(60).mean()  
            
            bias = ((close_px - ma20) / ma20) * 100  
            px_up = close_px > prev_px               
            vol_up = vol > vol_5ma                   
            
            # --- 溫和的均線格局判定 ---
            if close_px > ma5 > ma20 > ma60:
                trend_status = "🔥 多頭排列 (趨勢走強)" 
            elif close_px < ma5 < ma20 < ma60:
                trend_status = "🧊 空頭排列 (趨勢偏弱)" 
            elif close_px > ma60:
                trend_status = "🔼 站上季線 (波段看多)" 
            else:
                trend_status = "🔽 跌破季線 (波段防守)" 

            # --- 溫和的決策引擎 ---
            if current_type == "ETF":
                status = "存股觀察"
                if trend_status == "🔥 多頭排列 (趨勢走強)":
                    note = "🟢 長線趨勢佳，適合定期定額持有"
                elif trend_status == "🔼 站上季線 (波段看多)":
                    note = "🟡 穩步墊高，逢回踩月線可留意加碼"
                elif trend_status == "🔽 跌破季線 (波段防守)":
                    note = "⚪ 跌破均線支撐，建議暫緩加碼多觀察"
                else:
                    note = "⚪ 目前處於弱勢整理，建議多看少做"
            else:
                if px_up and vol_up:
                    status = "價漲量增"
                    note = "🟢 動能充足，維持強勢格局可續抱"
                elif px_up and not vol_up:
                    status = "價漲量縮"
                    note = "🟡 穩步墊高，持股續抱，空手宜觀望"
                elif not px_up and vol_up:
                    status = "價跌量增"
                    note = "🟠 短線賣壓湧現，請留意月線防守"
                else:
                    status = "價跌量縮"
                    note = "⚪ 量縮回檔，可觀察季線支撐力道"
                
            # 乖離率過大防護 (語氣放緩)
            if bias > 20:
                note = "🔥 短線漲幅較大 (乖離>20%)，可適度留意停利點"
                
            results.append({
                "代號": ticker.replace(".TW", ""), 
                "名稱": name,
                "現價": round(close_px, 2), 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "量價型態": status,
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

with st.spinner("系統正在讀取最新數據，請稍候..."):
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price, target_type)

if not final_data.empty:
    if target_type == "ETF":
        final_data = final_data.drop(columns=["量價型態"])
    st.dataframe(final_data, use_container_width=True, hide_index=True)
else:
    st.info("目前您選擇的板塊中，沒有符合預算的標的。您可以放寬「最高價位」或勾選更多產業。")

st.markdown("---")
st.caption("📝 說明：系統具備雙引擎判斷。個股偵測量價動能，ETF 專注長線存股趨勢。短線漲幅過大將溫和提示。資料自動快取更新。")
