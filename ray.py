import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ==========================================
# 頁面基本設定
# ==========================================
st.set_page_config(page_title="個人資產戰情室", layout="wide")
st.title("📊 個人資產與動態加碼戰情室")

# ==========================================
# 1. 樣式定義 (跌綠紅漲、負號、加碼亮燈)
# ==========================================
def color_profit_loss(val):
    if isinstance(val, (int, float)):
        if val < 0:
            return 'color: green; font-weight: bold;'
        elif val > 0:
            return 'color: red; font-weight: bold;'
    return ''

def highlight_buy_signal(val):
    if val == '🟢 觸發加碼':
        return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    return ''

# ==========================================
# 2. 初始個人投資組合設定 (已根據最新庫存更新)
# ==========================================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame([
        {"代號": "0056.TW", "名稱": "元大高股息", "成本價": 38.87, "股數": 20000, "單次配息": 1.0, "年配息次數": 4},
        {"代號": "00878.TW", "名稱": "國泰永續高股息", "成本價": 24.60, "股數": 22000, "單次配息": 0.4, "年配息次數": 4},
        {"代號": "00891.TW", "名稱": "中信關鍵半導體", "成本價": 33.97, "股數": 10000, "單次配息": 0.3, "年配息次數": 4},
        {"代號": "00927.TW", "名稱": "群益半導體收益", "成本價": 28.65, "股數": 20000, "單次配息": 0.4, "年配息次數": 4},
        {"代號": "0050.TW", "名稱": "元大台灣50", "成本價": 90.58, "股數": 0, "單次配息": 1.0, "年配息次數": 2}, 
        {"代號": "TBD1.TW", "名稱": "主動統一升級50", "成本價": 10.01, "股數": 5000, "單次配息": 0.0, "年配息次數": 0},
        {"代號": "TBD2.TW", "名稱": "主動統一台股增長", "成本價": 28.10, "股數": 15000, "單次配息": 0.0, "年配息次數": 0},
        {"代號": "TBD3.TW", "名稱": "主動群益台灣強棒", "成本價": 22.95, "股數": 10000, "單次配息": 0.0, "年配息次數": 0}
    ])

# ==========================================
# 3. 大盤與重點權值股監控
# ==========================================
st.header("🌐 大盤與重點權值股監控")
index_tickers = {
    "加權指數": "^TWII",
    "台指期(夜)": "TXF=F", 
    "台積電": "2330.TW",
    "聯發科": "2454.TW"
}

cols = st.columns(len(index_tickers))
for i, (name, ticker) in enumerate(index_tickers.items()):
    try:
        data = yf.Ticker(ticker).history(period="5d")
        if len(data) >= 2:
            close = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2]
            change = close - prev_close
            pct = (change / prev_close) * 100
            cols[i].metric(label=name, value=f"{close:,.2f}", delta=f"{change:+.2f} ({pct:+.2f}%)")
    except:
        cols[i].metric(label=name, value="無數據", delta="-")

st.divider()

# ==========================================
# 4. 爬取即時數據
# ==========================================
st.header("📋 投資組合與加碼明細")

@st.cache_data(ttl=300) 
def fetch_stock_data(tickers):
    data = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) >= 2:
                data[ticker] = {"現價": hist['Close'].iloc[-1], "昨日收盤": hist['Close'].iloc[-2]}
            else:
                data[ticker] = {"現價": 0, "昨日收盤": 0}
        except:
            data[ticker] = {"現價": 0, "昨日收盤": 0}
    return data

prices = fetch_stock_data(st.session_state.portfolio['代號'].tolist())

# ==========================================
# 5. 數據與損益計算
# ==========================================
df = st.session_state.portfolio.copy()

df['現價'] = df['代號'].apply(lambda x: prices.get(x, {}).get("現價", 0))
df['昨日收盤'] = df['代號'].apply(lambda x: prices.get(x, {}).get("昨日收盤", 0))

# 若抓不到現價 (例如 TBD 的代號)，自動以成本價替代，避免計算崩潰
df['現價'] = df.apply(lambda row: row['成本價'] if row['現價'] == 0 else row['現價'], axis=1)
df['昨日收盤'] = df.apply(lambda row: row['成本價'] if row['昨日收盤'] == 0 else row['昨日收盤'], axis=1)

df['總成本'] = df['成本價'] * df['股數']
df['總市值'] = df['現價'] * df['股數']
df['今日漲跌'] = (df['現價'] - df['昨日收盤']) * df['股數']
df['累積損益'] = df['總市值'] - df['總成本']

df['報酬率(%)'] = df.apply(lambda row: (row['累積損益'] / row['總成本']) * 100 if row['總成本'] > 0 else 0, axis=1)
df['預估年領息'] = df['單次配息'] * df['年配息次數'] * df['股數']

# 加碼觸價邏輯：持有股數大於 0，且現價跌破成本價 3%
df['加碼訊號'] = df.apply(lambda row: '🟢 觸發加碼' if row['股數'] > 0 and row['現價'] < (row['成本價'] * 0.97) else '-', axis=1)

# ==========================================
# 6. 介面呈現總覽
# ==========================================
total_value = df['總市值'].sum()
total_profit = df['累積損益'].sum()
total_daily = df['今日漲跌'].sum()
total_dividend = df['預估年領息'].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("總資產市值", f"${total_value:,.0f}")
c2.metric("累積總損益", f"${total_profit:+,.0f}")
c3.metric("今日總漲跌", f"${total_daily:+,.0f}")
c4.metric("預估年領息", f"${total_dividend:,.0f}")

st.write("") 

display_cols = ['代號', '名稱', '股數', '成本價', '現價', '加碼訊號', '今日漲跌', '累積損益', '報酬率(%)', '預估年領息']

st.dataframe(
    df[display_cols].style
    .map(color_profit_loss, subset=['今日漲跌', '累積損益', '報酬率(%)'])
    .map(highlight_buy_signal, subset=['加碼訊號'])
    .format({
        '股數': "{:,.0f}",
        '成本價': "{:.2f}",
        '現價': "{:.2f}",
        '今日漲跌': "{:+,.0f}",
        '累積損益': "{:+,.0f}",
        '報酬率(%)': "{:+.2f}%",
        '預估年領息': "{:,.0f}"
    }),
    use_container_width=True,
    height=320
)
