import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="NSE Sniper Pro", layout="wide", page_icon="🚀")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .big-font { font-size:18px !important; }
    .metric-box { border-left: 5px solid #007bff; background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    .profit { color: green; font-weight: bold; }
    .loss { color: red; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- TECHNICAL ANALYSIS ENGINE ---
@st.cache_data(ttl=3600)
def get_technicals(symbol):
    """Calculates MACD, RSI, and SMA Verdicts"""
    # Skip generic news placeholders
    if " " in symbol or len(symbol) > 15: return None 
    
    try:
        # Download 1 Year Data
        df = yf.download(f"{symbol}.NS", period="1y", progress=False)
        if df.empty: return None
        
        close = df['Close']
        curr_price = float(close.iloc[-1])
        
        # 1. SMA (Simple Moving Average)
        sma50 = close.rolling(window=50).mean().iloc[-1]
        sma200 = close.rolling(window=200).mean().iloc[-1]
        
        # 2. MACD (12, 26, 9)
        k = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        d = k.ewm(span=9, adjust=False).mean()
        macd_val = k.iloc[-1]
        signal_val = d.iloc[-1]
        
        # 3. RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # Verdict Logic
        score = 0
        if curr_price > sma200: score += 1
        if macd_val > signal_val: score += 1
        if 40 < rsi < 70: score += 1
        
        verdict = "NEUTRAL"
        if score == 3: verdict = "STRONG BUY 🟢"
        elif score == 2: verdict = "BUY 🟢"
        elif score == 0: verdict = "SELL 🔴"
        
        return {
            "Price": curr_price,
            "SMA200": sma200,
            "MACD": "Bullish" if macd_val > signal_val else "Bearish",
            "RSI": round(rsi, 2),
            "Verdict": verdict,
            "History": df['Close']
        }
    except:
        return None

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
except:
    st.error("Data missing. Please wait for GitHub Action to complete.")
    st.stop()

# --- SIDEBAR FILTERS (ALL RESTORED) ---
with st.sidebar:
    st.header("🔍 Filter Controls")
    
    # 1. Source Filter (Official vs Bulk vs Future)
    source_types = st.multiselect(
        "Data Source", 
        ["Official Filing", "Bulk Deal", "Future/Rumor"], 
        default=["Official Filing", "Bulk Deal", "Future/Rumor"]
    )
    
    # 2. Deal Value Filter (Slider + Input)
    show_all = st.checkbox("Show All Values (Ignore Filter)", value=False)
    if not show_all:
        min_val = st.number_input("Min Deal Value (Cr)", value=5.0, step=5.0)
    else:
        min_val = 0
        
    # 3. Time Filter
    days = st.selectbox("Lookback Period", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

# --- APPLY FILTERS ---
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

# Logic: Filter by Date AND Value AND Source
mask = (df['Date'] >= cutoff) & (df['Value_Cr'] >= min_val) & (df['Type'].isin(source_types))
filtered_df = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD LAYOUT ---
st.title("🚀 NSE Sniper Pro")
st.markdown(f"**{len(filtered_df)}** Opportunities Found")

tab_news, tab_tech = st.tabs(["📰 News & Deals", "📊 Technical Analysis"])

with tab_news:
    if filtered_df.empty:
        st.info("No deals found. Try checking 'Show All Values' in the sidebar.")
    else:
        for _, row in filtered_df.iterrows():
            with st.container(border=True):
                # Header Row
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"{row['Symbol']}")
                c1.caption(f"{row['Date'].strftime('%d-%b')} | {row['Type']}")
                
                # Value Badge
                if row['Value_Cr'] > 0:
                    c2.markdown(f"### ₹ {row['Value_Cr']} Cr")
                else:
                    c2.markdown("### --")
                
                # Content Row
                st.write(f"**{row['Headline']}**")
                
                with st.expander("📄 View Details & Technical Check"):
                    st.write(row['Details'])
                    
                    # Mini Technical Check inside the card
                    tech = get_technicals(row['Symbol'])
                    if tech:
                        st.divider()
                        st.markdown(f"**Analyst Verdict:** {tech['Verdict']}")
                        st.caption(f"Price: ₹{tech['Price']:.2f} | RSI: {tech['RSI']} | MACD: {tech['MACD']}")

with tab_tech:
    st.markdown("### 📈 Deep Dive Technicals")
    # Dropdown for available stocks in the filtered list
    stock_list = filtered_df[filtered_df['Symbol'].apply(lambda x: len(x)<15)]['Symbol'].unique()
    
    selected_stock = st.selectbox("Select Stock to Analyze", stock_list)
    
    if selected_stock:
        tech_data = get_technicals(selected_stock)
        
        if tech_data:
            # Verdict Banner
            st.info(f"VERDICT: {tech_data['Verdict']}")
            
            # Key Metrics
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Current Price", f"₹ {tech_data['Price']:.2f}")
            k2.metric("RSI (14)", tech_data['RSI'])
            k3.metric("MACD Signal", tech_data['MACD'])
            
            # Trend Check
            trend = "Bullish" if tech_data['Price'] > tech_data['SMA200'] else "Bearish"
            k4.metric("Long Term Trend", trend)
            
            # Chart
            st.line_chart(tech_data['History'])
        else:
            st.warning("Could not fetch chart data (Stock might be delisted or generic news).")
