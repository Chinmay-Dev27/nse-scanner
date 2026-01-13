import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(page_title="NSE Sniper Pro", layout="wide", page_icon="🎯")

# --- CUSTOM CSS (Formatting Fixes) ---
st.markdown("""
<style>
    /* Metric styling */
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
    
    /* Prevent text truncation */
    .stMarkdown p { white-space: normal; word-wrap: break-word; }
    
    /* Verdict badges */
    .verdict-strong-buy { background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-buy { background-color: #90EE90; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-sell { background-color: #dc3545; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .verdict-neutral { background-color: #e2e3e5; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- TECHNICAL ENGINE ---
@st.cache_data(ttl=3600)
def get_full_analysis(symbol):
    """Calculates Indicators (MACD, RSI, Vol)"""
    if not symbol or symbol in ["POTENTIAL NEWS", "MARKET NEWS"]: return None
    symbol = symbol.strip().replace(" ", "").upper()
    
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period="1y")
        if df.empty: return None
        
        close = df['Close']
        curr_price = close.iloc[-1]
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD
        k = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        d = k.ewm(span=9).mean()
        macd = "Bullish" if k.iloc[-1] > d.iloc[-1] else "Bearish"
        
        # SMA
        sma200 = close.rolling(200).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        
        # Volume
        vol_spike = "Yes" if df['Volume'].iloc[-1] > (1.5 * df['Volume'].rolling(20).mean().iloc[-1]) else "Normal"

        # PE (Graceful Fallback)
        try: pe = round(ticker.info.get('trailingPE', 0), 2)
        except: pe = "N/A"

        # Verdict
        score = 0
        if curr_price > sma200: score += 1
        if macd == "Bullish": score += 1
        if 40 < rsi < 70: score += 1
        
        verdict = "NEUTRAL"
        v_class = "verdict-neutral"
        if score >= 3: verdict, v_class = "STRONG BUY", "verdict-strong-buy"
        elif score == 2: verdict, v_class = "BUY", "verdict-buy"
        elif score == 0: verdict, v_class = "SELL", "verdict-sell"

        return {
            "History": df, "Price": curr_price, "RSI": rsi, "MACD": macd,
            "SMA_Cross": "Golden" if sma50 > sma200 else "Death", "PE": pe,
            "Volume": vol_spike, "Verdict": verdict, "Class": v_class
        }
    except: return None

def make_interactive_chart(df):
    data = df.tail(60).reset_index()
    data.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
    min_p, max_p = data['Close'].min() * 0.98, data['Close'].max() * 1.02
    
    chart = alt.Chart(data).mark_line(point=True).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%d %b', title='Date')),
        y=alt.Y('Close:Q', scale=alt.Scale(domain=[min_p, max_p]), title='Price'),
        tooltip=['Date:T', alt.Tooltip('Close', format=',.2f')]
    ).properties(height=250, width='container').interactive()
    return chart

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
except:
    st.error("Data missing. Please wait for the scanner to run.")
    st.stop()

# --- FILTERS ---
with st.sidebar:
    st.header("🔍 Filters")
    source = st.multiselect("Source", ["Official Filing", "Bulk Deal", "Future/Rumor"], default=["Official Filing", "Bulk Deal", "Future/Rumor"])
    show_all = st.checkbox("Show All Values", value=False)
    min_val = 0 if show_all else st.number_input("Min Deal Value (Cr)", value=5.0, step=5.0)
    days = st.selectbox("Timeframe", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

mask = (
    (df['Date'] >= cutoff) & 
    (df['Type'].isin(source)) & 
    ((df['Value_Cr'] >= min_val) | (df['Type'] == 'Future/Rumor')) 
)
filtered = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD ---
st.title("🎯 NSE Sniper Pro")
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
                c2.markdown(f"### ₹ {row['Value_Cr']:.2f} Cr") # Forced 2 decimals
            
            # CONTENT
            st.write(f"**{row['Headline']}**")
            
            # EXPANDER
            with st.expander("📊 Technical Analysis & Details"):
                st.write(row['Details'])
                
                if row['Symbol'] not in ["POTENTIAL NEWS"]:
                    st.divider()
                    st.markdown("### Deep Dive Analysis")
                    tech = get_full_analysis(row['Symbol'])
                    
                    if tech:
                        st.markdown(f"#### Verdict: <span class='{tech['Class']}'>{tech['Verdict']}</span>", unsafe_allow_html=True)
                        
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Price", f"₹ {tech['Price']:.2f}")
                        m2.metric("RSI (14)", f"{tech['RSI']:.2f}")
                        m3.metric("MACD", tech['MACD'])
                        m4.metric("PE Ratio", f"{tech['PE']}")
                        
                        st.markdown("#### Price Action (3 Months)")
                        st.altair_chart(make_interactive_chart(tech['History']), use_container_width=True)
                    else:
                        st.warning("Technical data unavailable.")
