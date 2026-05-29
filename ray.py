# --- 🧠 3. 核心運算引擎 (🔥加入 5, 20, 60 均線自動檢測🔥) ---

# @st.cache_data 這行就像是給程式吃「記憶吐司」。
# ttl=300 代表把算好的資料記住 300 秒 (5分鐘)。這樣你一直按重新整理，它也不會重新去 Yahoo 抓，保證秒開且不會當機。
@st.cache_data(ttl=300) 
def fetch_and_analyze(categories, universe_dict, price_limit):
    
    # 建立一個空的籃子，用來裝你剛剛在左邊勾選的那些股票（例如你勾了半導體，就把台積電、聯電裝進來）
    tickers_to_fetch = {}
    for cat in categories:
        tickers_to_fetch.update(universe_dict[cat])
    
    # 如果籃子是空的（你什麼都沒勾），就直接結束，畫面不顯示東西
    if not tickers_to_fetch:
        return pd.DataFrame()

    results = [] # 準備一個大表格，用來存放等一下算好的所有結果
    
    # 開始一檔一檔把籃子裡的股票拿出來算
    for ticker, name in tickers_to_fetch.items():
        try:
            # 告訴 Yahoo Finance：「我要抓這支股票的資料」
            tk = yf.Ticker(ticker)
            
            # 抓取過去 6 個月 (6mo) 的歷史資料。因為要算 60 日季線，所以至少要抓 6 個月才夠算
            hist = tk.history(period="6mo")
            
            # 如果這支股票沒有資料，或者上市不到 60 天（算不出季線），就跳過它，換下一支
            if hist.empty or len(hist) < 60: continue
            
            # .iloc[-1] 代表「最後一筆資料」，也就是「今天的收盤價」
            close_px = hist['Close'].iloc[-1]
            
            # ⛔ 價格安檢門：如果今天收盤價比你設定的「最高價位」還要貴，直接跳過不看！
            if close_px > price_limit: continue
            
            # .iloc[-2] 代表「倒數第二筆資料」，也就是「昨天的收盤價」
            prev_px = hist['Close'].iloc[-2]
            
            # 把今天的成交股數除以 1000，換算成我們習慣看的「張數」
            vol = hist['Volume'].iloc[-1] / 1000  
            
            # ⛔ 流動性安檢門：如果是「個股」，且今天成交量不到 1000 張，代表太冷門，直接跳過不看！
            if vol < 1000 and target_type == "個股": continue 

            # --- 📈 均線與技術計算 ---
            # 算過去 5 天的平均成交量 (5日均量)
            vol_5ma = (hist['Volume'].tail(5).mean()) / 1000
            
            # 算平均股價 (MA = Moving Average)
            ma5 = hist['Close'].tail(5).mean()    # 過去 5 天平均 (周線)
            ma20 = hist['Close'].tail(20).mean()  # 過去 20 天平均 (月線)
            ma60 = hist['Close'].tail(60).mean()  # 過去 60 天平均 (季線)
            
            # 算乖離率：(今天股價 - 月線) / 月線 * 100。用來判斷是不是漲過頭了
            bias = ((close_px - ma20) / ma20) * 100  
            
            # 判斷今天有沒有漲 (今天價格 > 昨天價格)
            px_up = close_px > prev_px               
            # 判斷今天量有沒有放大 (今天成交量 > 5天平均成交量)
            vol_up = vol > vol_5ma                   
            
            # --- 🎯 均線趨勢自動判定 ---
            if close_px > ma5 > ma20 > ma60:
                trend_status = "🔥 多頭排列 (極強)" # 股價在最上面，三條線往上，超強！
            elif close_px < ma5 < ma20 < ma60:
                trend_status = "🧊 空頭排列 (極弱)" # 股價在最下面，被壓著打，超弱！
            elif close_px > ma60:
                trend_status = "🔼 站上季線 (偏多)" # 至少還在生命線(季線)之上
            else:
                trend_status = "🔽 跌破季線 (偏空)" # 跌破生命線了，要小心

            # --- 🤖 自動決策備註邏輯 (你最需要的判斷助手) ---
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
                
            # 如果乖離率超過 10% (漲離月線太遠了)，系統強制蓋過前面的建議，發出危險警告！
            if bias > 10:
                note = "🔥 乖離率過大，極度危險勿追高！"
                
            # 把上面算好的所有資料，打包成一行一行的表格資料
            results.append({
                "代號": ticker.replace(".TW", ""), # 把 .TW 拿掉，畫面比較乾淨
                "名稱": name,
                "現價": round(close_px, 2), # round(xx, 2) 代表小數點只留兩位
                "5MA": round(ma5, 2),
                "20MA": round(ma20, 2),
                "60MA": round(ma60, 2),
                "均線格局": trend_status,  
                "成交量(張)": int(vol),
                "狀態": status,
                "🤖 系統建議": note
            })
        except:
            # 如果這支股票抓資料時發生任何錯誤，就直接跳過，不要讓整個程式當機
            continue
            
    # 把剛剛打包好的一行一行資料，正式轉換成一個大表格 (DataFrame)
    df = pd.DataFrame(results)
    
    # 如果表格裡面有資料，就把這張表按照「成交量(張)」從大到小排序
    if not df.empty:
        df = df.sort_values(by="成交量(張)", ascending=False)
        
    return df # 把最後排好序的表格交出去給畫面顯示
