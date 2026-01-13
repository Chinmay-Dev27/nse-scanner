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
    .metric-box { border-left: 5px solid #007bff; background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    .verdict-buy { color: #28a745; font-weight: bold; background-color: #d4edda; padding: 2px 6px; border-radius: 4px; }
    .verdict-sell { color: #dc3545; font-weight: bold; background-color: #f8d7da; padding: 2px 6px; border-radius: 4px; }
    .verdict-neutral { color: #6c757d; font-weight: bold; background-color: #e2e3e5; padding: 2px 6px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# --- CHART ENGINE (RESTORED) ---
@st.cache_data(ttl=3600)
def get_stock_data(symbol):
    """Fetches 1mo history for sparklines & technicals"""
    if not symbol or symbol in ["POTENTIAL NEWS", "MARKET NEWS"]: return None
    # CLEANER: Remove spaces again just in case
    symbol = symbol.strip().replace(" ", "").upper()
    
    try:
        ticker = f"{symbol}.NS"
        df = yf.download(ticker, period="1mo", progress=False)
        if df.empty: return None
        return df
    except: return None

def make_sparkline(df):
    """Creates the 7-day trend chart with Dynamic Scaling"""
    if df is None or df.empty: return None
    
    # Prep Data
    hist = df['Close'].tail(10).reset_index()
    hist.columns = ['Date', 'Close']
    
    # Dynamic Scale (Min/Max)
    min_p = hist['Close'].min() * 0.995
    max_p = hist['Close'].max() * 1.005
    
    # Color Logic (Green if up, Red if down)
    start = hist['Close'].iloc[0]
    end = hist['Close'].iloc[-1]
    line_color = '#28a745' if end >= start else '#dc3545'

    chart = alt.Chart(hist).mark_line(color=line_color, strokeWidth=2).encode(
        x=alt.X('Date', axis=None),
        y=alt.Y('Close', scale=alt.Scale(domain=[min_p, max_p]), axis=None),
        tooltip=['Date', 'Close']
    ).properties(height=60, width=150)
    
    return chart

def calculate_technicals(df):
    """Returns verdict based on RSI/MACD"""
    if df is None: return None
    try:
        close = df['Close']
        curr = float(close.iloc[-1])
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain/loss
        rsi = 100 - (100/(1+rs)).iloc[-1]
        
        # MACD
        k = close.ewm(span=12).mean() - close.ewm(span=26).mean()
        d = k.ewm(span=9).mean()
        macd = "Bullish" if k.iloc[-1] > d.iloc[-1] else "Bearish"
        
        score = 0
        if 40 < rsi < 70: score += 1
        if macd == "Bullish": score += 1
        
        verdict = "NEUTRAL"
        if score == 2: verdict = "BUY"
        elif score == 0: verdict = "SELL"
        
        return {"Price": curr, "RSI": round(rsi,2), "MACD": macd, "Verdict": verdict}
    except: return None

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
except:
    st.error("Data missing. Please wait for GitHub Action.")
    st.stop()

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🔍 Filter Controls")
    source = st.multiselect("Data Source", ["Official Filing", "Bulk Deal", "Future/Rumor"], default=["Official Filing", "Bulk Deal", "Future/Rumor"])
    
    # RESTORED VALUE FILTER
    show_all = st.checkbox("Show All Values", value=False)
    min_val = 0 if show_all else st.number_input("Min Deal Value (Cr)", value=5.0, step=5.0)
    
    days = st.selectbox("Lookback", ["Last 24h", "Last 3 Days", "Last 30 Days"], index=1)

# --- FILTER LOGIC ---
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 30 Days": 30}
cutoff = datetime.now() - timedelta(days=d_map[days])

mask = (
    (df['Date'] >= cutoff) & 
    (df['Type'].isin(source)) & 
    ((df['Value_Cr'] >= min_val) | (df['Type'] == 'Future/Rumor')) 
)
filtered = df[mask].sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD ---
st.title("🚀 NSE Sniper Pro")
st.markdown(f"**{len(filtered)}** Opportunities Found")

if filtered.empty:
    st.info("No deals found.")
else:
    for _, row in filtered.iterrows():
        # Get Data Once
        stock_data = get_stock_data(row['Symbol'])
        
        with st.container(border=True):
            # ROW 1: Header + Value Badge
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"{row['Symbol']}")
            c1.caption(f"{row['Date'].strftime('%d-%b')} | {row['Type']}")
            if row['Value_Cr'] > 0:
                c2.markdown(f"### ₹ {row['Value_Cr']} Cr")
            
            # ROW 2: Headline + Sparkline Chart
            col_txt, col_chart = st.columns([2, 1])
            with col_txt:
                st.write(f"**{row['Headline']}**")
            with col_chart:
                if stock_data is not None:
                    st.altair_chart(make_sparkline(stock_data), use_container_width=True)
                else:
                    if row['Symbol'] not in ["POTENTIAL NEWS"]:
                        st.caption("No Chart")
            
            # ROW 3: Expander with Technicals
            with st.expander("🔍 Details & Analysis"):
                st.write(row['Details'])
                if stock_data is not None:
                    st.divider()
                    tech = calculate_technicals(stock_data)
                    if tech:
                        t1, t2, t3, t4 = st.columns(4)
                        t1.metric("Price", f"₹{tech['Price']:.2f}")
                        t2.metric("Verdict", tech['Verdict'])
                        t3.metric("RSI", tech['RSI'])
                        t4.metric("MACD", tech['MACD'])
