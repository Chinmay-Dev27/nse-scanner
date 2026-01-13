import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="NSE Sniper Pro", layout="wide", page_icon="🚀")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .metric-box { border-left: 5px solid #007bff; background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    .verdict-buy { color: #28a745; font-weight: bold; background-color: #d4edda; padding: 2px 6px; border-radius: 4px; }
    .verdict-sell { color: #dc3545; font-weight: bold; background-color: #f8d7da; padding: 2px 6px; border-radius: 4px; }
    .verdict-neutral { color: #6c757d; font-weight: bold; background-color: #e2e3e5; padding: 2px 6px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- TECHNICAL ANALYSIS ENGINE ---
@st.cache_data(ttl=3600)
def get_technicals(symbol):
    """Calculates MACD, RSI, and SMA Verdicts"""
    # CLEAN INPUT
    if not symbol or symbol in ["POTENTIAL NEWS", "MARKET NEWS"]: return None
    symbol = symbol.strip().upper()
    
    # Validation
    if len(symbol) > 15 or " " in symbol: return None

    try:
        # Download Data (Ensure .NS suffix)
        ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        df = yf.download(ticker, period="1y", progress=False)
        
        if df.empty: return None
        
        close = df['Close']
        curr_price = float(close.iloc[-1])
        
        # Indicators
        sma200 = close.rolling(window=200).mean().iloc[-1]
        
        # MACD
        k = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        d = k.ewm(span=9, adjust=False).mean()
        macd_val = k.iloc[-1]
        signal_val = d.iloc[-1]
        
        # RSI
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
        css_class = "verdict-neutral"
        
        if score == 3: 
            verdict = "STRONG BUY"
            css_class = "verdict-buy"
        elif score == 2: 
            verdict = "BUY"
            css_class = "verdict-buy"
        elif score == 0: 
            verdict = "SELL"
            css_class = "verdict-sell"
        
        return {
            "Price": curr_price,
            "SMA200": sma200,
            "MACD": "Bullish" if macd_val > signal_val else "Bearish",
            "RSI": round(rsi, 2),
            "Verdict": verdict,
            "Class": css_class,
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

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🔍 Filter Controls")
    
    source_types = st.multiselect(
        "Data Source", 
        ["Official Filing", "Bulk Deal", "Future/Rumor"], 
        default=["Official Filing", "Bulk Deal", "Future/Rumor"]
    )
    
    # Deal Value Filter
    show_all = st.checkbox("Show All Values (Ignore Filter)", value=True)
    if not show_all:
        min_val = st.number_input("Min Deal Value (Cr)", value=5.0, step=5.0)
    else:
        min_val = 0
        
    days = st.selectbox("Lookback Period", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

# --- APPLY FILTERS ---
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

# FIXED LOGIC: Always show 'Future/Rumor' even if value is 0
mask = (
    (df['Date'] >= cutoff) & 
    (df['Type'].isin(source_types)) & 
    ((df['Value_Cr'] >= min_val) | (df['Type'] == 'Future/Rumor')) 
)

filtered_df = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD LAYOUT ---
st.title("🚀 NSE Sniper Pro")
st.markdown(f"**{len(filtered_df)}** Opportunities Found")

if filtered_df.empty:
    st.info("No deals found.")
else:
    for _, row in filtered_df.iterrows():
        with st.container(border=True):
            # Header
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"{row['Symbol']}")
            c1.caption(f"{row['Date'].strftime('%d-%b')} | {row['Type']}")
            
            # Value Badge
            if row['Value_Cr'] > 0:
                c2.markdown(f"### ₹ {row['Value_Cr']} Cr")
            
            # Headline
            st.write(f"**{row['Headline']}**")
            
            # UNIFIED EXPANDER: Details + Technicals
            with st.expander("🔍 Analyze & Details"):
                st.write(row['Details'])
                
                # Logic Check: Only run technicals if it's NOT a rumor
                if row['Symbol'] not in ["POTENTIAL NEWS", "MARKET NEWS"]:
                    st.divider()
                    st.markdown("### 📊 Technical Snapshot")
                    
                    tech = get_technicals(row['Symbol'])
                    
                    if tech:
                        # VERDICT ROW
                        v1, v2 = st.columns([1, 3])
                        v1.markdown(f"Verdict: <span class='{tech['Class']}'>{tech['Verdict']}</span>", unsafe_allow_html=True)
                        v2.caption("Based on SMA200, MACD & RSI")
                        
                        # METRICS ROW
                        k1, k2, k3 = st.columns(3)
                        k1.metric("Price", f"₹ {tech['Price']:.2f}")
                        k2.metric("RSI (14)", tech['RSI'])
                        k3.metric("MACD", tech['MACD'])
                        
                        # CHART
                        st.line_chart(tech['History'], height=250)
                    else:
                        st.warning(f"Could not load chart for {row['Symbol']}. (Might be a new listing or symbol mismatch)")
                else:
                    st.caption("Technical analysis not available for generic/future news.")
