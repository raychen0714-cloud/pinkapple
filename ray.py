import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
import xml.etree.ElementTree as ET

# --- ⚙️ 頁面與效能設定 ---
st.set_page_config(page_title="PRO 級存股戰情室", layout="wide")

# --- 💾 永久記憶系統 (絕對路徑鎖死版 + 防崩潰機制) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "user_data.json")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"⚠️ 資料檔案讀取錯誤，暫時使用預設值以防崩潰: {e}")
            pass # 繼續往下回傳預設值
            
    return {
        "total_div": 0.0,
        "max_price": 1000.0,
        "custom_div_map": {
            "00919.TW": "1.0元",
            "00918.TW": "1.26元",
            "0056.TW": "1.0元" 
        },
        "held_stocks": ["00878.TW", "00919.TW", "00918.TW", "0056.TW", "00927.TW"],
        "manual_tickers": "878, 919, 918, 0056, 927, 0052, 2409, 6116, 3481"
    }

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush() # 強制刷新記憶體到硬碟
            os.fsync(f.fileno()) # 強制同步寫入，防止檔案鎖定歸零
    except Exception as e:
        st.error(f"❌ 存檔失敗: {e}")

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
                st.session_state.app_data["total_div"] += float(amount_input)
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

# --- 📰 即時新聞攔截引擎 ---
@st.cache_data(ttl=1800)
def fetch_realtime_news(keyword):
    try:
        url = f"https://news.google.com/rss/search?q={keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        res = requests.get(url, timeout=5)
        root = ET.fromstring(res.content)
        news_list = []
        for item in root.findall('.//channel/item')[:5]:
            title = item.find('title').text
            link = item.find('link').text
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

# --- 📝 專屬自訂名稱字典 (擴充海量熱門 ETF 版) ---
CUSTOM_NAME_MAP = {
    # 你的自訂與個股 (保留你原本的命名)
    "4958.TW": "臻鼎-KY", "3037.TW": "四欣技", "3481.TW": "群創", "2887.TW": "台新金",
    "00981A.TW": "瑤姊", "00631L.TW": "元大正2", "00685L.TW": "群益正2",
    
    # 凱基系列 (補上你指定的 009816)
    "009816.TW": "凱基台灣TOP50",
    
    # 高股息與市值型人氣 ETF
    "0050.TW": "元大台灣50", "0052.TW": "富邦科技", "0056.TW": "元大高股息",
    "00878.TW": "國泰永續高股息", "00919.TW": "群益精選高息", "00929.TW": "復華台灣科技優息",
    "00713.TW": "元大台灣高息低波", "00915.TW": "凱基優選高股息", "00918.TW": "大華優利高填息",
    "00927.TW": "群益半導體收益", "00939.TW": "統一台灣高息動能", "00940.TW": "元大台灣價值高息",
    "00881.TW": "國泰台灣5G+", "00891.TW": "中信關鍵半導體", "00900.TW": "富邦特選高股息",
    "00692.TW": "富邦公司治理", "00850.TW": "元大臺灣ESG", "00923.TW": "群益台ESG低碳",
    
    # 債券與其他熱門 ETF
    "00679B.TW": "元大美債20年", "00687B.TW": "國泰20年美債", "00937B.TW": "群益ESG投等債",
    "00751B.TW": "元大AAA至A公司債", "00720B.TW": "元大投資級公司債", "00772B.TW": "中信高評級公司債"
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

# 強制將 current_max 轉為 float，避免與 number_input 的 step 衝突
current_max = float(st.session_state.app_data.get("max_price", 1000.0))
max_price = st.sidebar.number_input("3. 設定最高價位 (元)", value=current_max, step=10.0)

if max_price != current_max:
    st.session_state.app_data["max_price"] = max_price
    save_data(st.session_state.app_data)
    st.rerun()  

st.sidebar.markdown("---")
only_manual = st.sidebar.checkbox("🎯 只看自選標的 (隱藏系統清單)", value=False)

saved_tickers = st.session_state.app_data.get("manual_tickers", "878, 919, 918, 0056, 927, 0052, 2409, 6116")
manual_tickers_str = st.sidebar.text_input(
    "🔍 4. 手動新增觀察標的", 
    value=saved_tickers, 
    placeholder="如: 878, 56, 3481"
)

if manual_tickers_str != saved_tickers:
    st.session_state.app_data["manual_tickers"] = manual_tickers_str
    save_data(st.session_state.app_data)
    st.rerun()

# --- 🧠 3. 核心運算引擎 ---
@st.cache_data(ttl=30)  
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
                if ticker in CUSTOM_NAME_MAP: 
                    name = CUSTOM_NAME_MAP[ticker]
                else:
                    try:
                        real_name = tk.info.get("shortName")
                        if real_name: 
                            # 🛡️ 版面保護盾：如果名字超過 8 個字 (特別是英文)，強制截斷並加上 ..
                            name = real_name[:8] + ".." if len(real_name) > 8 else real_name
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
            
            close_px = np.nan
            try:
                close_px = float(tk.fast_info.last_price)
            except: pass
                
            if np.isnan(close_px) or close_px <= 0:
                try:
                    today_live = tk.history(period="1d", interval="1m")
                    if not today_live.empty:
                        close_px = float(today_live['Close'].iloc[-1])
                except: pass
            
            if np.isnan(close_px) or close_px <= 0:
                close_px = float(hist['Close'].iloc[-1])
                
            if not is_manual and close_px > price_limit: continue
            
            try:
                prev_close = float(hist['Close'].iloc[-2])
                price_change_abs = close_px - prev_close 
                price_change_pct = (price_change_abs / prev_close) * 100 
                
                if price_change_abs > 0:
                    change_str = f"🔺 +{price_change_pct:.2f}% / +{price_change_abs:.2f}"
                elif price_change_abs < 0:
                    change_str = f"🔻 {price_change_pct:.2f}% / {price_change_abs:.2f}"
                else:
                    change_str = "➖ 0.00% / 0.00"
            except:
                change_str = "➖ 0.00% / 0.00"

            vol = float(hist['Volume'].iloc[-1]) / 1000  
            if not is_manual and vol < 1000 and current_type == "個股": continue 

            vol_5ma = float(hist['Volume'].tail(5).mean()) / 1000
            ma5 = float(hist['Close'].tail(5).mean())   
            ma20 = float(hist['Close'].tail(20).mean())  
            ma60 = float(hist['Close'].tail(60).mean()) if len(hist) >= 60 else 0 
            
            bias = ((close_px - ma20) / ma20) * 100  
            px_up = close_px > prev_close                
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

            # --- 🔥 將 K 線圖示改為專業純文字解析 ---
            try:
                O = float(hist['Open'].iloc[-1])
                H = max(float(hist['High'].iloc[-1]), close_px)
                L = min(float(hist['Low'].iloc[-1]), close_px)
                C = close_px
                body = abs(C - O)
                up_shadow = H - max(O, C)
                dn_shadow = min(O, C) - L
                tr = H - L
                
                k_msg = "形態平穩"
                if tr > 0:
                    if body / tr >= 0.6:
                        if C >= O: k_msg = "強勢紅K"
                        else: k_msg = "疲軟黑K"
                    elif up_shadow > body * 1.5 and up_shadow > dn_shadow * 1.5:
                        if C >= O: k_msg = "上影線(賣壓)"
                        else: k_msg = "長上影線(重壓)"
                    elif dn_shadow > body * 1.5 and dn_shadow > up_shadow * 1.5:
                        if C >= O: k_msg = "下影線(買盤)"
                        else: k_msg = "下影線(止跌)"
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
                "📈 漲跌": change_str, 
                "成交量(張)": int(vol),
                "趨勢格局": trend_status,  
                "📊 官方籌碼": current_chip,  
                "🤖 系統建議": note,
                "Yahoo配息": yahoo_div_info 
            })
        except: continue
            
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["成交量(張)"], ascending=[False])
        df.reset_index(drop=True, inplace=True)
    return df 

# --- 📊 4. 畫面渲染 (頂部選單區) ---
col_menu1, col_menu2 = st.columns(2)

with col_menu1:
    with st.expander("📊 K線型態速查對照表 (純文字解析版)", expanded=False):
        st.markdown("#### 第一組：明確趨勢 (實體為主)")
        st.markdown("- **[強勢紅K]**：買盤強勁，收盤價高於開盤價且實體長。多頭格局，可續抱或加碼。")
        st.markdown("- **[疲軟黑K]**：賣壓較大，收盤價低於開盤價。短線回檔，觀察是否跌破支撐。")
        st.markdown("---")
        st.markdown("#### 第二組：高檔遇壓 (上影線系列)")
        st.markdown("- **[上影線(賣壓)]**：盤中曾衝高但遇壓回落，買盤力道減弱。留意上方壓力，勿追高。")
        st.markdown("- **[長上影線(重壓)]**：出現長上影線，代表上方賣壓極重。建議減碼，嚴控風險。")
        st.markdown("---")
        st.markdown("#### 第三組：低檔有撐 (下影線系列)")
        st.markdown("- **[下影線(買盤)]**：盤中曾殺低但有買盤接手，支撐力道強。有鐵板護盤，可逢低布局。")
        st.markdown("- **[下影線(止跌)]**：盤中殺低後拉回，顯示賣壓漸竭。勿恐慌殺低，觀察明日反彈。")

with col_menu2:
    with st.expander("🌍 國際財經與大老動態 (即時新聞)", expanded=False):
        tab_jensen, tab_trump, tab_finance = st.tabs(["👑 黃仁勳動態", "🦅 川普發言", "📈 今日財經焦點"])
        
        with tab_jensen:
            st.caption("每 30 分鐘自動攔截最新動態")
            news_jensen = fetch_realtime_news("黃仁勳 OR 輝達 OR NVIDIA")
            for item in news_jensen:
                st.markdown(f"➤ [{item['title']}]({item['link']})")
                
        with tab_trump:
            st.caption("關注關稅與地緣政治談話")
            news_trump = fetch_realtime_news("川普 OR Trump 股市")
            for item in news_trump:
                st.markdown(f"➤ [{item['title']}]({item['link']})")
                
        with tab_finance:
            st.caption("台股大盤與財經要聞")
            news_finance = fetch_realtime_news("台股 OR 聯準會 OR 降息")
            for item in news_finance:
                st.markdown(f"➤ [{item['title']}]({item['link']})")

st.markdown("---")
st.subheader(f"🔍 PRO 觀察雷達 (最高價 {max_price} 元以下)")

with st.spinner("真實證券報價、官方籌碼與配息資料同步中..."):
    final_data = fetch_and_analyze(selected_categories, active_universe, max_price, target_type, manual_tickers_str, only_manual)

if not final_data.empty:
    def assign_final_dividend(row):
        t_key = row['原始代號']
        if t_key in st.session_state.app_data["custom_div_map"]:
            return st.session_state.app_data["custom_div_map"][t_key]
        return row['Yahoo配息']

    final_data['💰 最新配息'] = final_data.apply(assign_final_dividend, axis=1)
    
    held_list = st.session_state.app_data.get("held_stocks", [])
    final_data['📌 持有'] = final_data['原始代號'].apply(lambda x: x in held_list)
    final_data['標的'] = final_data['代號'].astype(str) + " " + final_data['名稱']
    
    display_df = final_data[['📌 持有', '原始代號', '標的', '現價', '📈 漲跌', '成交量(張)', '📊 官方籌碼', '趨勢格局', '🤖 系統建議', '💰 最新配息']]
    display_df = display_df.sort_values(by=["📌 持有", "成交量(張)"], ascending=[False, False]).reset_index(drop=True)
    
    def color_tw_stock(val):
        if isinstance(val, str):
            if '🔺' in val:
                return 'color: #ff4b4b; font-weight: bold;' 
            elif '🔻' in val:
                return 'color: #09ab3b; font-weight: bold;' 
        return ''

    if hasattr(display_df.style, "map"):
        styled_df = display_df.style.map(color_tw_stock, subset=['📈 漲跌'])
    else:
        styled_df = display_df.style.applymap(color_tw_stock, subset=['📈 漲跌'])
    
    # --- 🔥 強制鎖死寬度配置，防止配息欄位被擠掉 ---
    edited_df = st.data_editor(
        styled_df,
        key="portfolio_editor", 
        hide_index=True,
        use_container_width=True, 
        disabled=["標的", "現價", "📈 漲跌", "📊 官方籌碼", "趨勢格局", "🤖 系統建議"], 
        column_config={
            "📌 持有": st.column_config.CheckboxColumn("📌 持有", width=60),
            "原始代號": None, 
            "標的": st.column_config.TextColumn("標的", width=140), 
            "現價": st.column_config.NumberColumn("現價", format="$%.2f", width=80),
            "📈 漲跌": st.column_config.TextColumn("📈 漲跌", width=120), 
            "成交量(張)": st.column_config.NumberColumn("成交量", width=80),
            "📊 官方籌碼": st.column_config.TextColumn("📊 籌碼", width=120),
            "趨勢格局": st.column_config.TextColumn("趨勢", width=100), 
            "🤖 系統建議": st.column_config.TextColumn("🤖 建議", width=200), # 限制此欄寬度
            "💰 最新配息": st.column_config.TextColumn("💰 配息", width=160) # 給予足夠顯示空間
        }
    )

    # 暴力比對迴圈：一有修改，立刻存檔
    has_changes = False
    current_held = st.session_state.app_data.get("held_stocks", [])

    for i in range(len(display_df)):
        ticker_key = display_df.iloc[i]['原始代號']
        
        old_held = bool(display_df.iloc[i]['📌 持有'])
        new_held = bool(edited_df.iloc[i]['📌 持有'])
        if old_held != new_held:
            if new_held and (ticker_key not in current_held):
                current_held.append(ticker_key)
            elif (not new_held) and (ticker_key in current_held):
                current_held.remove(ticker_key)
            has_changes = True

        old_div = str(display_df.iloc[i]['💰 最新配息'])
        new_div = str(edited_df.iloc[i]['💰 最新配息'])
        if old_div != new_div:
            st.session_state.app_data["custom_div_map"][ticker_key] = new_div
            has_changes = True

    if has_changes:
        st.session_state.app_data["held_stocks"] = current_held
        save_data(st.session_state.app_data)       
        st.session_state.show_save_success = True  
        st.rerun()

    # --- 📊 新增：每日戰績熱力追蹤 (自動換行小方塊版) ---
    st.markdown("---")
    st.subheader("🎯 持股每日戰績追蹤")
    col_perf1, col_perf2 = st.columns([2, 5])

    with col_perf1:
        perf_period = st.selectbox("選擇追蹤區間", ["近1個月", "近3個月", "近6個月"], index=0)
        period_map = {"近1個月": "1mo", "近3個月": "3mo", "近6個月": "6mo"}

    # 篩選出所有打勾「持有」的標的
    held_data = final_data[final_data['📌 持有'] == True]

    if not held_data.empty:
        html_output = ""
        for _, row in held_data.iterrows():
            tk = yf.Ticker(row['原始代號'])
            hist = tk.history(period=period_map[perf_period])
            
            if len(hist) < 2:
                continue
                
            # 計算每日漲跌幅
            hist['Prev_Close'] = hist['Close'].shift(1)
            hist['Pct_Change'] = ((hist['Close'] - hist['Prev_Close']) / hist['Prev_Close']) * 100
            hist = hist.dropna(subset=['Pct_Change'])
            
            # 建立小方塊 HTML (含日期與漲跌幅)
            boxes_html = ""
            for date, h_row in hist.iterrows():
                pct = h_row['Pct_Change']
                date_str = date.strftime("%m/%d") # 顯示月/日
                
                # 根據漲跌判定顏色
                if pct > 0:
                    color = "#ff4b4b"      # 紅字
                    bg_color = "#ffeeee"   # 淺紅底
                    pct_str = f"+{pct:.1f}%"
                elif pct < 0:
                    color = "#09ab3b"      # 綠字
                    bg_color = "#eeffee"   # 淺綠底
                    pct_str = f"{pct:.1f}%"
                else:
                    color = "#888888"      # 灰字
                    bg_color = "#f5f5f5"   # 淺灰底
                    pct_str = "0.0%"
                    
                # 【修正重點】：強制單行，不留任何前導縮排空白，防止 Streamlit 誤判為程式碼區塊
                boxes_html += f"""<div style="display:inline-block; background-color:{bg_color}; color:{color}; padding:4px 6px; margin:3px; border-radius:6px; font-size:13px; border:1px solid {color}; text-align:center; min-width:45px;"><div style="font-size:10px; color:#555; margin-bottom:2px;">{date_str}</div><div style="font-weight:bold; font-family:monospace;">{pct_str}</div></div>"""
                
            # 將該檔股票的所有方塊包裝起來 (同樣強制單行)
            html_output += f"""<div style="margin-bottom:20px; padding:15px; background-color:#ffffff; border:1px solid #e0e0e0; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.05);"><h5 style="margin-top:0; margin-bottom:10px; color:#1e3c72; border-bottom:2px solid #f0f2f6; padding-bottom:5px;">📌 {row['標的']}</h5><div style="display:flex; flex-wrap:wrap;">{boxes_html}</div></div>"""
            
        if html_output:
            # 輸出渲染 HTML
            st.markdown(html_output, unsafe_allow_html=True)
        else:
            st.warning("無足夠歷史資料可供計算。")
    else:
        st.info("尚未勾選任何持有標的，請在上方雷達表打勾後即可查看。")
        # --- 🔍 核心成分股 ETF 權重透視矩陣 (最終穩定版) ---
st.markdown("---")
st.subheader("🔍 核心成分股 ETF 權重透視矩陣")

# 這是你的核心資料庫，直接在這裡修改數字即可！
# 格式為: "股票代號": {"ETF代號": 權重數字}
ETF_DATA = {
    "2330.TW": {"0050.TW": 53.5, "0052.TW": 64.42},
    "2454.TW": {"0050.TW": 4.5, "0052.TW": 7.02},
    "3037.TW": {"00929.TW": 4.2},
    "2317.TW": {"0050.TW": 5.1, "0052.TW": 0.47},
    "2327.TW": {"00919.TW": 2.5},
    "2308.TW": {"0050.TW": 3.2},
    "2383.TW": {"00891.TW": 4.5}
}

search_stocks = {
    "2330.TW": "台積電", "2454.TW": "聯發科", "3711.TW": "日月光投控",
    "3037.TW": "欣興", "2303.TW": "聯電", "2317.TW": "鴻海",
    "6147.TW": "頎邦", "4958.TW": "臻鼎-KY",
    "2327.TW": "國巨", "2308.TW": "台達電", "2383.TW": "台光電"
}

all_etfs = ["0050.TW", "0052.TW", "00878.TW", "00919.TW", "00929.TW", "00927.TW"]

# 構建矩陣數據
matrix_data = []
for etf in all_etfs:
    row = {"代號": etf.replace(".TW", ""), "ETF 名稱": CUSTOM_NAME_MAP.get(etf, etf.replace(".TW", ""))}
    for stock_code, stock_name in search_stocks.items():
        # 如果資料庫裡有這檔 ETF 對應這檔股票的權重就讀取，沒有就顯示 "-"
        weight = ETF_DATA.get(stock_code, {}).get(etf, 0)
        row[stock_name] = f"{weight:.2f}%" if weight > 0 else "-"
    matrix_data.append(row)

# 顯示表格
df_final = pd.DataFrame(matrix_data)
st.dataframe(df_final, hide_index=True, use_container_width=True)
else:
    st.warning("權重數據載入失敗，請檢查 weights.json 是否存在。")
