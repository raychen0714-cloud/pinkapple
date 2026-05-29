import streamlit as st
import yfinance as yf
import pandas as pd

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 戰情室", layout="wide")
st.title("🚀 PRO 級自動化決策戰情室")
st.markdown("---")

# --- 📂 1. 定義標的池 (🔥 超級擴充版大水庫 🔥) ---
STOCK_UNIVERSE = {
    "半導體": {
        "2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "3711.TW": "日月光投控", 
        "3034.TW": "聯詠", "2379.TW": "瑞昱", "2344.TW": "華邦電", "2408.TW": "南亞科", 
        "3443.TW": "創意", "3661.TW": "世芯-KY", "6415.TW": "矽力-KY", "8046.TW": "南電", 
        "3189.TW": "景碩", "3037.TW": "欣興", "5347.TW": "世界先進", "6239.TW": "力成",
        "2338.TW": "光罩", "3583.TW": "辛耘", "3131.TW": "弘塑"
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

max_price = st.sidebar.number_input("3. 設定最高價位 (元)", value=50, step=5)

# --- 🧠 3. 核心運算引擎 (全中文註解 + 均線偵測 + 無名次限制) ---
@st.cache_data(ttl=300) 
def fetch_and_analyze(categories, universe_dict, price_limit):
    
    # 建立一個空的籃子，用來裝你剛剛在左邊勾選的那些股票
    tickers_to_fetch = {}
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat])
    
    # 如果籃子是空的，就直接結束
    if not tickers_to_fetch:
        return pd.DataFrame()

    results = [] # 準備一個大表格存放結果
    
    # 開始一檔一檔算
    for ticker, name in tickers_to_fetch.items():
        try:
            tk = yf.Ticker(ticker)
            # 抓取過去 6 個月 (6mo) 的歷史資料，算季線必須抓 6 個月
            hist = tk.history(period="6mo")
            
            if hist.empty or len(hist) < 60: continue
            
            close_px = hist['Close'].iloc[-1]
            
            # ⛔ 價格安檢門
            if close_px > price_limit: continue
            
            prev_px = hist['Close'].iloc[-2]
            vol = hist['Volume'].iloc[-1] / 1000  
            
            # ⛔ 流動性安檢門：成交量不到 1000 張跳過
            if
