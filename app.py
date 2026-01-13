import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="InvestSmart Scanner", layout="wide", page_icon="💹")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    .verdict-bull { color: #27ae60; font-weight: bold; font-size: 1.1em; }
    .verdict-bear { color: #c0392b; font-weight: bold; font-size: 1.1em; }
    .stExpander { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# --- FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_stock_data(symbol):
    """Fetches data and calculates returns"""
    if " " in symbol or len(symbol) > 15: return None # Skip generic news
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        # Get 1 month history to calculate trends
        hist = ticker.history(period="1mo")
        if hist.empty: return None
        return hist
    except:
        return None

def make_sparkline(hist_data):
    """Creates a dynamic Altair chart scaled to Min/Max"""
    hist_data = hist_data.reset_index()
    hist_data['Date'] = hist_data['Date'].dt.strftime('%d-%b')
    
    # DYNAMIC SCALING: Set domain to strictly min and max of the data
    min_p = hist_data['Close'].min() * 0.99
    max_p = hist_data['Close'].max() * 1.01
    
    chart = alt.Chart(hist_data).mark_line(strokeWidth=2).encode(
        x=alt.X('Date', axis=None), # Hide X axis for clean look
        y=alt.Y('Close', scale=alt.Scale(domain=[min_p, max_p]), axis=None), # Dynamic Scale
        color=alt.value("#2980b9") # Professional Blue
    ).properties(height=60, width=150)
    
    return chart

# --- APP LAYOUT ---
st.title("💹 Smart Investment Scanner")
st.markdown("Automated intelligence from **NSE Filings** and **Tier-1 Financial News**.")

# LOAD DATA
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values(by=['Date', 'Value_Cr'], ascending=[False, False])
except:
    st.error("Data not found. Please run the scanner.")
    st.stop()

# --- FILTERS ---
with st.sidebar:
    st.header("🎯 Filter Opportunities")
    min_deal = st.number_input("Min Deal Value (Cr)", value=0.0, step=10.0)
    sentiment = st.multiselect("News Sentiment", ["Positive", "Negative"], default=["Positive"])
    days = st.selectbox("Timeframe", ["Last 24h", "Last 3 Days", "Last 7 Days"], index=1)

# Apply Filters
d_map = {"Last 24h": 1, "Last 3 Days": 3, "Last 7 Days": 7}
start_date = datetime.now() - timedelta(days=d_map[days])
filtered = df[
    (df['Date'] >= start_date) & 
    (df['Sentiment'].isin(sentiment)) & 
    (df['Value_Cr'] >= min_deal)
]

# --- DISPLAY ---
col_kpi1, col_kpi2 = st.columns(2)
col_kpi1.metric("Deals Found", len(filtered))
col_kpi2.metric("Avg Deal Value", f"₹ {int(filtered['Value_Cr'].mean()) if not filtered.empty else 0} Cr")

st.divider()

if filtered.empty:
    st.info("No deals found matching your criteria.")
else:
    for _, row in filtered.iterrows():
        # Fetch stock data for guidance
        hist = get_stock_data(row['Symbol'])
        
        with st.container():
            # LAYOUT: [ Info (4) | Verdict (2) | Chart (2) ]
            c1, c2, c3 = st.columns([4, 2, 2])
            
            with c1:
                st.subheader(row['Symbol'])
                st.caption(f"📅 {row['Date'].strftime('%d %b')} | Source: {row['Type']}")
                st.write(f"**{row['Headline']}**")
                if row['Value_Cr'] > 0:
                    st.markdown(f"💰 **Value: ₹ {row['Value_Cr']} Cr**")

            with c2:
                # INVESTMENT GUIDANCE ENGINE
                st.markdown("**Analyst Verdict:**")
                if hist is not None:
                    curr_price = hist['Close'].iloc[-1]
                    wk_change = ((curr_price - hist['Close'].iloc[-7]) / hist['Close'].iloc[-7]) * 100
                    
                    # Logic: Good News + Uptrend = Strong Buy
                    if row['Sentiment'] == "Positive":
                        if wk_change > 0:
                            st.markdown("🟢 <span class='verdict-bull'>Momentum Buy</span>", unsafe_allow_html=True)
                            st.caption(f"Stock is UP {wk_change:.1f}% this week.")
                        else:
                            st.markdown("🟡 <span class='verdict-bull'>Value Pick?</span>", unsafe_allow_html=True)
                            st.caption(f"Good news but stock down {wk_change:.1f}%.")
                    else:
                        st.markdown("🔴 <span class='verdict-bear'>Caution</span>", unsafe_allow_html=True)
                else:
                    st.caption("Market data unavailable")

            with c3:
                # ALTAIR SPARKLINE
                if hist is not None:
                    st.altair_chart(make_sparkline(hist.tail(15)), use_container_width=True)
                else:
                    st.write("No Chart")
            
            with st.expander("Show Details"):
                st.write(row['Details'])
                
            st.divider()
