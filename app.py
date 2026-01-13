import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="NSE Sniper Pro", layout="wide", page_icon="🚀")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .metric-box { background-color: #f8f9fa; border-radius: 5px; padding: 10px; border-left: 4px solid #007bff; }
    .tech-pass { color: #28a745; font-weight: bold; }
    .tech-fail { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- TECHNICAL ANALYSIS ENGINE ---
@st.cache_data(ttl=3600)
def get_technicals(symbol):
    """Calculates MACD, RSI, and SMA Verdicts"""
    if " " in symbol or len(symbol) > 15: return None # Skip junk
    try:
        # Download 1 Year Data
        df = yf.download(f"{symbol}.NS", period="1y", progress=False)
        if df.empty: return None
        
        # Calculate Indicators
        close = df['Close']
        
        # 1. SMA
        sma50 = close.rolling(window=50).mean().iloc[-1]
        sma200 = close.rolling(window=200).mean().iloc[-1]
        curr_price = float(close.iloc[-1])
        
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
        verdict = "NEUTRAL"
        score = 0
        if curr_price > sma200: score += 1
        if macd_val > signal_val: score += 1
        if rsi < 70 and rsi > 40: score += 1
        
        if score == 3: verdict = "STRONG BUY 🟢"
        elif score == 2: verdict = "BUY 🟢"
        elif score == 0: verdict = "SELL 🔴"
        
        return {
            "Price": curr_price,
            "SMA50": sma50,
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
    st.error("Data missing. Run scraper first.")
    st.stop()

# --- SIDEBAR FILTERS (RESTORED) ---
with st.sidebar:
    st.header("🔍 Filter Controls")
    
    # 1. Data Source Filter (Restored Bulk Deals)
    source_types = st.multiselect(
        "Data Source", 
        ["Official Filing", "Bulk Deal", "Future/Rumor"], 
        default=["Official Filing", "Bulk Deal", "Future/Rumor"]
    )
    
    # 2. Deal Value Filter (Restored)
    min_val = st.number_input("Min Deal Value (Cr)", value=0, step=10, help="Set to 0 to see all")
    
    # 3. Time Filter
    days = st.selectbox("Lookback", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

# Apply Filters
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

mask = (df['Date'] >= cutoff) & (df['Value_Cr'] >= min_val) & (df['Type'].isin(source_types))
filtered_df = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- MAIN DASHBOARD ---
st.title("🚀 NSE Sniper Pro")
st.markdown(f"**{len(filtered_df)}** Opportunities Found | Highest Deal: **₹ {filtered_df['Value_Cr'].max() if not filtered_df.empty else 0} Cr**")

tab_news, tab_tech = st.tabs(["📰 News & Deals", "📊 Technical Analysis"])

with tab_news:
    if filtered_df.empty:
        st.info("No deals found. Try lowering the Value Filter.")
    else:
        for _, row in filtered_df.iterrows():
            with st.container(border=True):
                # Header
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"{row['Symbol']} { '🔥' if row['Value_Cr'] > 100 else ''}")
                c1.caption(f"{row['Date'].strftime('%d-%b')} | {row['Type']}")
                
                # Deal Value Badge
                if row['Value_Cr'] > 0:
                    c2.markdown(f"### ₹ {row['Value_Cr']} Cr")
                else:
                    c2.caption("Value Undisclosed")
                
                # Details
                st.write(f"**{row['Headline']}**")
                with st.expander("Show Details"):
                    st.write(row['Details'])
                    
                    # Technical Snippet inside News Card
                    tech = get_technicals(row['Symbol'])
                    if tech:
                        st.markdown("---")
                        st.markdown(f"**Quick Tech Verdict:** {tech['Verdict']}")
                        st.caption(f"RSI: {tech['RSI']} | MACD: {tech['MACD']}")

with tab_tech:
    st.markdown("### 📈 Deep Dive Technicals")
    selected_stock = st.selectbox("Select Stock to Analyze", filtered_df['Symbol'].unique())
    
    if selected_stock:
        tech_data = get_technicals(selected_stock)
        
        if tech_data:
            # Verdict Banner
            st.info(f"VERDICT: {tech_data['Verdict']}")
            
            # Metrics
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Current Price", f"₹ {tech_data['Price']:.2f}")
            k2.metric("RSI (14)", tech_data['RSI'])
            k3.metric("MACD Signal", tech_data['MACD'])
            
            # SMA Logic
            sma_status = "Bullish" if tech_data['Price'] > tech_data['SMA200'] else "Bearish"
            k4.metric("Trend (200 SMA)", sma_status)
            
            # Chart
            st.markdown("#### Price Trend (1 Year)")
            st.line_chart(tech_data['History'])
            
        else:
            st.warning("Could not fetch technical data (Symbol might be generic news).")
