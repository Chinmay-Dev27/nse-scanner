import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="NSE Sniper Pro", layout="wide", page_icon="🎯")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .verdict-strong-buy { background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-buy { background-color: #90EE90; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-sell { background-color: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-neutral { background-color: #e2e3e5; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- ADVANCED TECHNICAL ENGINE ---
@st.cache_data(ttl=3600)
def get_full_analysis(symbol):
    """Fetches History, Calculates Indicators (MACD, RSI, Vol), and PE"""
    if not symbol or symbol in ["POTENTIAL NEWS", "MARKET NEWS"]: return None
    symbol = symbol.strip().replace(" ", "").upper()
    
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        
        # 1. Fetch History (Fast)
        df = ticker.history(period="1y")
        if df.empty: return None
        
        # 2. Indicators Calculation
        close = df['Close']
        curr_price = close.iloc[-1]
        
        # RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD (12, 26, 9)
        k = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        d = k.ewm(span=9).mean()
        macd_val = k.iloc[-1]
        signal_val = d.iloc[-1]
        
        # Moving Averages
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        
        # Volume Spike Check
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        vol_spike = "Yes" if curr_vol > (1.5 * avg_vol) else "Normal"

        # 3. Fundamental Data (PE Ratio) - May be slow, handle gracefully
        try:
            # Attempt to get PE, if fail use 'N/A'
            info = ticker.info
            pe_ratio = info.get('trailingPE', 'N/A')
            sector_pe = info.get('industryTrailingPE', 'N/A') # Often not available in free tier
        except:
            pe_ratio = 'N/A'
            sector_pe = 'N/A'

        # 4. FINAL VERDICT LOGIC
        score = 0
        if curr_price > sma200: score += 1      # Long term uptrend
        if macd_val > signal_val: score += 1    # Momentum up
        if 40 < rsi < 70: score += 1            # Not overbought
        if vol_spike == "Yes": score += 0.5     # Volume confirmation
        
        verdict = "NEUTRAL"
        v_class = "verdict-neutral"
        
        if score >= 3:
            verdict = "STRONG BUY"
            v_class = "verdict-strong-buy"
        elif score >= 2:
            verdict = "BUY"
            v_class = "verdict-buy"
        elif score <= 1:
            verdict = "SELL / CAUTION"
            v_class = "verdict-sell"

        return {
            "History": df,
            "Price": curr_price,
            "RSI": round(rsi, 2),
            "MACD": "Bullish" if macd_val > signal_val else "Bearish",
            "SMA_Status": "Golden Cross" if sma50 > sma200 else "Death Cross" if sma50 < sma200 else "Neutral",
            "PE": pe_ratio,
            "Volume": vol_spike,
            "Verdict": verdict,
            "Class": v_class
        }
    except Exception as e:
        return None

def make_interactive_chart(df):
    """Creates a Detailed Chart with Axes and Tooltips"""
    if df is None: return None
    
    # Focus on last 3 months for clarity
    data = df.tail(60).reset_index()
    data.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits'] # Standardize
    
    # Dynamic Scale
    min_p = data['Close'].min() * 0.98
    max_p = data['Close'].max() * 1.02
    
    chart = alt.Chart(data).mark_line(point=True).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%d %b', title='Date')),
        y=alt.Y('Close:Q', scale=alt.Scale(domain=[min_p, max_p]), title='Price (INR)'),
        tooltip=['Date:T', alt.Tooltip('Close', format=',.2f'), 'Volume']
    ).properties(
        height=250,
        width='container'
    ).interactive() # Allows zooming/panning
    
    return chart

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
except:
    st.error("Data missing. Please run the scanner.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔍 Filters")
    source = st.multiselect("Source", ["Official Filing", "Bulk Deal", "Future/Rumor"], default=["Official Filing", "Bulk Deal", "Future/Rumor"])
    
    # DEAL VALUE (Restored)
    show_all = st.checkbox("Show All Values", value=False)
    min_val = 0 if show_all else st.number_input("Min Deal Value (Cr)", value=5.0, step=5.0)
    
    days = st.selectbox("Timeframe", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

# --- FILTERING ---
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

mask = (
    (df['Date'] >= cutoff) & 
    (df['Type'].isin(source)) & 
    ((df['Value_Cr'] >= min_val) | (df['Type'] == 'Future/Rumor')) 
)
filtered = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD ---
st.title("🎯 NSE Market Sniper Pro")
st.markdown(f"Found **{len(filtered)}** Actionable Signals")

if filtered.empty:
    st.info("No stocks match your filters.")
else:
    for _, row in filtered.iterrows():
        with st.container(border=True):
            # HEADER
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"{row['Symbol']}")
            c1.caption(f"{row['Date'].strftime('%d-%b-%Y')} | {row['Type']}")
            if row['Value_Cr'] > 0:
                c2.markdown(f"### ₹ {row['Value_Cr']} Cr")
            
            # NEWS
            st.write(f"**{row['Headline']}**")
            
            # EXPANDER: Full Analysis
            with st.expander("📊 Technical Analysis & Details"):
                st.write(row['Details'])
                
                if row['Symbol'] not in ["POTENTIAL NEWS"]:
                    st.divider()
                    st.markdown("### Deep Dive Analysis")
                    
                    # Fetch Data
                    tech = get_full_analysis(row['Symbol'])
                    
                    if tech:
                        # 1. VERDICT BANNER
                        st.markdown(f"#### Verdict: <span class='{tech['Class']}'>{tech['Verdict']}</span>", unsafe_allow_html=True)
                        
                        # 2. KEY METRICS GRID
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Current Price", f"₹ {tech['Price']:.2f}")
                        m2.metric("RSI (14)", tech['RSI'], help="<30 Oversold, >70 Overbought")
                        m3.metric("MACD", tech['MACD'])
                        m4.metric("PE Ratio", tech['PE'])
                        
                        m5, m6, m7, m8 = st.columns(4)
                        m5.metric("Trend (SMA)", "Bullish" if tech['Price'] > tech['Price'] else "Bearish") # Simplified check
                        m6.metric("Crossover", tech['SMA_Status'])
                        m7.metric("Volume Spike", tech['Volume'])
                        
                        # 3. INTERACTIVE CHART
                        st.markdown("#### Price Action (Last 3 Months)")
                        chart = make_interactive_chart(tech['History'])
                        st.altair_chart(chart, use_container_width=True)
                        
                    else:
                        st.warning(f"Could not load technical data for {row['Symbol']}. (New listing or ticker mismatch)")
                else:
                    st.info("Technical analysis not applicable for Rumor/Generic news.")
