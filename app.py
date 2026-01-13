import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from datetime import datetime, timedelta

# --- PAGE SETUP ---
st.set_page_config(page_title="Market Sniper", layout="wide", page_icon="🎯")

# --- CSS FOR UI ---
st.markdown("""
<style>
    .big-price { font-size: 24px; font-weight: bold; color: #2c3e50; }
    .trend-up { color: #27ae60; font-weight: bold; }
    .trend-down { color: #c0392b; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# --- FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_stock_history(symbol):
    """
    Robust fetcher: Tries NSE first, handles failures gracefully.
    Returns: DataFrame with history, Current Price, Percent Change
    """
    # Clean symbol (remove spaces, special chars if any)
    clean_sym = symbol.replace('&', '').strip()
    
    try:
        ticker = yf.Ticker(f"{clean_sym}.NS")
        hist = ticker.history(period="1mo")
        
        if hist.empty:
            # Fallback: Try BSE? Or just return None
            return None, 0, 0
            
        curr_price = hist['Close'].iloc[-1]
        start_price = hist['Close'].iloc[0]
        change_pct = ((curr_price - start_price) / start_price) * 100
        
        return hist, curr_price, change_pct
    except:
        return None, 0, 0

def plot_interactive_chart(hist_data):
    """Altair chart with TOOLTIPS and AXES"""
    if hist_data is None: return None
    
    hist_data = hist_data.reset_index()
    
    # Base chart
    base = alt.Chart(hist_data).encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%d-%b', title='')),
        tooltip=['Date:T', alt.Tooltip('Close', format=',.2f')]
    )

    # Line
    line = base.mark_line(color='#2962FF').encode(
        y=alt.Y('Close:Q', scale=alt.Scale(zero=False), title='Price (₹)')
    )
    
    return line.properties(height=200, width='container')

# --- MAIN APP ---
st.title("🎯 NSE Market Sniper")

# LOAD DATA
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
except:
    st.error("Data missing. Please run 'scraper.py' via GitHub Actions.")
    st.stop()

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.header("⚙️ Scanner Settings")
    
    # 1. TIME FILTER
    time_period = st.radio("Lookback Period", ["Last 24 Hours", "Last 7 Days", "Last 30 Days"])
    
    # 2. DEAL VALUE
    show_all = st.checkbox("Show All (Include Small Deals)", value=True)
    if not show_all:
        min_val = st.slider("Min Deal Value (Cr)", 0, 5000, 50)
    else:
        min_val = 0

# FILTER LOGIC
today = datetime.now()
if time_period == "Last 24 Hours":
    start_date = today - timedelta(days=1)
elif time_period == "Last 7 Days":
    start_date = today - timedelta(days=7)
else:
    start_date = today - timedelta(days=30)

filtered = df[(df['Date'] >= start_date) & (df['Value_Cr'] >= min_val)].copy()
filtered = filtered.sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- TABS FOR PAST vs FUTURE ---
tab_past, tab_future = st.tabs(["📢 Past News (Filings)", "🔮 Future Events (Board Meetings)"])

with tab_past:
    st.caption("Official NSE Announcements & Bulk Deals")
    
    if filtered.empty:
        st.info("No news found for this period.")
    else:
        for idx, row in filtered.iterrows():
            with st.container(border=True):
                # HEADLINE ROW
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"{row['Symbol']}")
                if row['Value_Cr'] > 0:
                    c2.metric("Deal Value", f"₹ {row['Value_Cr']} Cr")
                
                # CONTENT ROW
                col_info, col_chart = st.columns([1, 1])
                
                with col_info:
                    st.write(f"**{row['Headline']}**")
                    st.caption(f"📅 {row['Date'].strftime('%d %b %Y')} | Sentiment: {row['Sentiment']}")
                    with st.expander("Details"):
                        st.write(row['Details'])

                with col_chart:
                    # Fetch live data
                    hist, price, chg = get_stock_history(row['Symbol'])
                    
                    if hist is not None:
                        # Price + Trend Display
                        color = "trend-up" if chg >= 0 else "trend-down"
                        arrow = "🔼" if chg >= 0 else "🔻"
                        st.markdown(f"<span class='big-price'>₹ {price:.2f}</span> <span class='{color}'>({arrow} {chg:.1f}%)</span>", unsafe_allow_html=True)
                        
                        # Render Chart
                        st.altair_chart(plot_interactive_chart(hist), use_container_width=True)
                    else:
                        st.warning("⚠️ Market data unavailable for this ticker.")

with tab_future:
    st.caption("Upcoming Board Meetings & Agendas")
    # Filter for future events
    future_events = df[df['Type'] == 'Future Event']
    
    if future_events.empty:
        st.info("No upcoming board meetings found.")
    else:
        st.dataframe(
            future_events[['Date', 'Symbol', 'Headline']], 
            use_container_width=True,
            hide_index=True
        )
