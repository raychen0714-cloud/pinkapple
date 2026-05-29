import streamlit as st
import yfinance as yf
import pandas as pd

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 戰情室", layout="wide")
st.title("🚀 PRO 級自動化決策戰情室")
st.markdown("---")

# --- 📂 1. 定義標的池 (🔥已加入中文名稱與擴充產業🔥) ---
# 使用字典格式，讓程式可以秒抓名稱，不用等 Yahoo 慢慢查
STOCK_UNIVERSE = {
    "半導體": {"2330.TW": "台積電", "2303.TW": "聯電", "2454.TW": "聯發科", "3711.TW": "日月光", "3034.TW": "聯詠"},
    "光電與面板": {"3481.TW": "群創", "2409.TW": "友達", "6116.TW": "彩晶"},
    "航運": {"2603.TW": "長榮", "2609.TW": "陽明", "2615.TW": "萬海", "2610.TW": "華航", "2618.TW": "長榮航"},
    "電子與電腦周邊": {"2317.TW": "鴻海", "2382.TW": "廣達", "3231.TW": "緯創", "2356.TW": "英業達", "2324.TW": "仁寶"},
    "金融": {"2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金", "2886.TW": "兆豐金"},
    "重電與綠能": {"1519.TW": "華城", "1503.TW": "士電", "1513.TW": "中興電", "1514.TW": "亞力"},
    "營建與鋼鐵": {"2002.TW": "中鋼", "2520.TW": "冠德", "2548.TW": "華固", "2014.TW": "中鴻"}
}

ETF_UNIVERSE = {
    "高股息": {"00878.TW": "國泰永續高股息", "0056.TW": "元大高股息", "00919.TW": "群益精選高息", "00929.TW": "復華科技優息"},
    "半導體與科技": {"00927.TW": "群益半導體收益", "00881.TW": "國泰台灣5G+", "00891.TW": "中信關鍵半導體"},
    "大盤與其他": {"006208.TW": "富邦台50", "00631L.TW": "元大台灣50正2"} 
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

# --- 🧠 3. 核心運算引擎 (加入快取與自動決策邏輯) ---
@st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求 Yahoo 導致變慢
def fetch_and_analyze(categories, universe_dict, price_limit):
    # 組合要查詢的代號與名稱字典
    tickers_to_fetch = {}
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat])
    
    if not tickers_to_fetch:
        return pd.DataFrame()

    results = []
    for ticker, name in tickers_to_fetch.items():
        try:
            tk = yf.Ticker(ticker)
            # 抓取近 1 個月資料來算 20日線 (月線) 與均量
            hist = tk.history(period="1mo")
            if hist.empty or len(hist) < 20: continue
            
            close_px = hist['Close'].iloc[-1]
            
            # ⛔ 價格過濾器 (大於設定價位直接略過)
            if close_px > price_limit: continue
            
            prev_px = hist['Close'].iloc[-2]
            vol = hist['Volume'].iloc[-1] / 1000  # 轉成張數
            
            # ⛔ 流動性過濾器 (成交量太小的殭屍股直接略過)
            if vol < 1000 and target_type == "個股": continue 

            vol_5ma = (hist['Volume'].tail(5).mean()) / 1000
            ma20 = hist['Close'].tail(20).mean()
            
            # --- 數學運算 ---
            bias = ((close_px - ma20) / ma20) * 100  # 乖離率
            px_up = close_px > prev_px               # 價漲
            vol_up = vol > vol_5ma                   # 量增 (大於5日均量)
            
            # --- 🤖 自動決策備註邏輯 ---
            if px_up and vol_up:
                status = "價漲量增"
                note = "🟢 燃料充足，可續抱或觀察"
            elif px_up and not vol_up:
                status = "價漲量縮 (頂背離)"
                note = "⚠️ 追價力道弱，注意獲利了結"
            elif not px_up and vol_up:
                status = "價跌量增"
                note = "🚨 賣壓沉重，請避開勿接刀"
            else:
                status = "價跌量縮"
                note = "⚪ 賣壓減輕，可觀察築底"
                
            # 乖離率防護機制 (覆蓋原本建議)
            if bias > 10:
                note = "🔥 乖離率過大，極度危險勿追高！"
                
            results.append({
                "代號": ticker.replace(".TW", ""),
                "名稱": name,  # 🔥 這裡把中文名字加進來了！
                "現價": round(close_px, 2),
                "成交量(張)": int(vol),
                "狀態": status,
                "乖離率(%)": round(bias, 2),
                "🤖 系統建議": note
            })
        except:
            continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        # 只取成交量最大的前 5 名
        df = df.sort_values(by="成交量(張)", ascending=False).head(5)
    return df

# --- 📊 4. 畫面渲染 ---
st.subheader(f"🔍 {target_type} 觀察雷達 (最高價 {max_price} 元以下)")

with st.spinner("系統正在進行量價分析與背離過濾，請稍候..."):
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price)

if not final_data.empty:
    # 使用 Streamlit 原生表格，隱藏 index 讓畫面更乾淨
    st.dataframe(final_data, use_container_width=True, hide_index=True)
else:
    st.info("目前您選擇的產業中，沒有符合預算且具備流動性的標的。您可以嘗試放寬「最高價位」或勾選更多產業。")

st.markdown("---")
st.caption("📝 說明：系統已自動過濾流動性不足之標的。乖離率 > 10% 系統將自動發出防追高警示。資料來源為 Yahoo Finance，自動每 5 分鐘快取更新。")
