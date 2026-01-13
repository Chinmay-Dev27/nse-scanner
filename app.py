import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- PAGE SETUP ---
st.set_page_config(page_title="NSE Market Pulse", layout="wide", page_icon="📈")

# --- CUSTOM CSS FOR MODERN UI ---
st.markdown("""
<style>
    /* badges */
    .badge-pos { background-color: #d1e7dd; color: #0f5132; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .badge-neg { background-color: #f8d7da; color: #842029; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .badge-neu { background-color: #e2e3e5; color: #41464b; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    
    /* deal value typography */
    .deal-value { font-size: 1.5rem; font-weight: 700; color: #2E86C1; }
    .deal-label { font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 1px; }
    
    /* remove default chart margin */
    .stChart { margin-top: -20px; }
</style>
""", unsafe_allow_html=True)

# --- CACHED FUNCTIONS (Speed Optimization) ---
@st.cache_data(ttl=3600) # Cache price data for 1 hour
def get_price_trend(symbol):
    """Fetches last 7 days closing prices for sparkline chart."""
    try:
        # NSE symbols in Yahoo Finance need '.NS' suffix
        ticker = f"{symbol}.NS"
        stock = yf.Ticker(ticker)
        # Fetch 10 days to ensure we get 7 trading days
        hist = stock.history(period="10d")
        return hist['Close'].tail(7)
    except:
        return None

def load_data():
    try:
        df = pd.read_csv("nse_data.csv")
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df
    except FileNotFoundError:
        return pd.DataFrame()

# --- SIDEBAR FILTERS ---
st.sidebar.title("🔍 Scanner Controls")

# 1. Precise Value Filter (Number Input > Slider)
min_val = st.sidebar.number_input(
    "Min Deal Value (Cr)", 
    min_value=0.0, 
    value=2.0, 
    step=0.5,
    help="Filter out small deals. Set to 0 to see everything."
)

# 2. Time Filter
time_options = {"Today": 1, "Last 3 Days": 3, "Last Week": 7, "Last Month": 30}
selected_time = st.sidebar.selectbox("Time Period", list(time_options.keys()), index=1)
days_back = time_options[selected_time]

# 3. Sentiment Filter
selected_sentiment = st.sidebar.multiselect(
    "Sentiment", 
    ["Positive", "Negative", "Neutral"], 
    default=["Positive", "Negative"]
)

# --- MAIN APP LOGIC ---
st.title("📈 NSE Actionable Intelligence")
st.caption("Real-time corporate filings & bulk deals with price context.")

df = load_data()

if df.empty:
    st.info("⚠️ No data found. Please ensure the 'scanner.py' script has run successfully.")
    st.stop()

# Filter Data
cutoff_date = datetime.now() - timedelta(days=days_back)
mask = (
    (df['Date'] >= cutoff_date) & 
    (df['Sentiment'].isin(selected_sentiment)) & 
    (df['Value_Cr'] >= min_val)
)
filtered_df = df.loc[mask].copy()

# Sort: Biggest deals first
filtered_df = filtered_df.sort_values(by='Value_Cr', ascending=False)

# Top Metrics
m1, m2, m3 = st.columns(3)
m1.metric("Deals Found", len(filtered_df))
total_val = filtered_df['Value_Cr'].sum()
m2.metric("Total Deal Value", f"₹ {total_val:,.0f} Cr")
m3.metric("Top Sector", "Cap Goods (Est.)") # Placeholder for future sector logic

st.divider()

# --- DISPLAY CARDS ---
if filtered_df.empty:
    st.warning("No stocks match your filters. Try lowering the deal value.")
else:
    for index, row in filtered_df.iterrows():
        # Create a visual card container
        with st.container(border=True):
            # ROW 1: Header (Symbol + Badge)
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"🏢 {row['Symbol']}")
                st.caption(f"{row['Date'].strftime('%d %b %Y')} • {row['Source']}")
            with c2:
                # Badge Logic
                s_color = "badge-pos" if row['Sentiment'] == "Positive" else "badge-neg" if row['Sentiment'] == "Negative" else "badge-neu"
                st.markdown(f'<span class="{s_color}">{row["Sentiment"].upper()}</span>', unsafe_allow_html=True)

            st.markdown("---")

            # ROW 2: Content + Chart
            col_details, col_chart = st.columns([2, 1])
            
            with col_details:
                # Headline
                st.markdown(f"**{row['Headline']}**")
                
                # Deal Value Display
                if row['Value_Cr'] > 0:
                    st.markdown(f"""
                    <div style="margin-top:10px;">
                        <span class="deal-label">Estimated Value</span><br>
                        <span class="deal-value">₹ {row['Value_Cr']} Cr</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                with st.expander("📄 Read Full Details"):
                    st.write(row['Details'])

            with col_chart:
                # Price Trend Sparkline
                st.caption("7-Day Price Trend")
                chart_data = get_price_trend(row['Symbol'])
                if chart_data is not None and not chart_data.empty:
                    # Color line based on trend (Green if up, Red if down)
                    start_p = chart_data.iloc[0]
                    end_p = chart_data.iloc[-1]
                    color = "#008000" if end_p >= start_p else "#FF0000"
                    
                    st.line_chart(chart_data, height=100, color=color)
                else:
                    st.caption("Chart unavail.")

