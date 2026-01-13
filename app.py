import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="NSE Smart Scanner", layout="wide", page_icon="📊")

# Custom CSS for Green/Red styling
st.markdown("""
<style>
    .positive { color: #0f5132; background-color: #d1e7dd; padding: 5px; border-radius: 5px; font-weight: bold; }
    .negative { color: #842029; background-color: #f8d7da; padding: 5px; border-radius: 5px; font-weight: bold; }
    .big-money { font-size: 1.1em; font-weight: bold; color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

st.title("📊 NSE Actionable Market Scanner")

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    # Convert Date column to datetime objects for filtering
    # NSE dates usually come as 'DD-Mon-YYYY' or ISO. We handle standard parsing.
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
except:
    st.error("No data found. Run the scanner first.")
    st.stop()

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🔍 Filters")

# 1. TIME PERIOD
time_filter = st.sidebar.radio(
    "Select Time Period", 
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"]
)

# 2. SENTIMENT
sentiment_filter = st.sidebar.multiselect(
    "Impact Type",
    ["Positive", "Negative", "Neutral"],
    default=["Positive", "Negative"]
)

# 3. MINIMUM DEAL VALUE
min_val = st.sidebar.slider("Minimum Deal Value (Cr)", 0, 5000, 0, step=10)

# --- FILTERING LOGIC ---
today = datetime.now()

if time_filter == "Last 24 Hours":
    start_date = today - timedelta(days=1)
elif time_filter == "Last 7 Days":
    start_date = today - timedelta(days=7)
elif time_filter == "Last 30 Days":
    start_date = today - timedelta(days=30)
else:
    start_date = df['Date'].min()

# Apply Filters
mask = (
    (df['Date'] >= start_date) & 
    (df['Sentiment'].isin(sentiment_filter)) &
    (df['Value_Cr'] >= min_val)
)
filtered_df = df.loc[mask].copy()

# Sort by Value (Highest First)
filtered_df = filtered_df.sort_values(by=['Value_Cr', 'Date'], ascending=[False, False])

# --- DASHBOARD ---

# Top metrics
col1, col2, col3 = st.columns(3)
col1.metric("Opportunities Found", len(filtered_df))
col2.metric("Highest Deal Value", f"₹ {filtered_df['Value_Cr'].max()} Cr" if not filtered_df.empty else "0")
col3.metric("Positive vs Negative", 
            f"{len(filtered_df[filtered_df['Sentiment']=='Positive'])} / {len(filtered_df[filtered_df['Sentiment']=='Negative'])}")

st.divider()

# --- DISPLAY CARDS ---
if not filtered_df.empty:
    for _, row in filtered_df.iterrows():
        # Define card color border based on sentiment
        border_color = "green" if row['Sentiment'] == "Positive" else "red"
        
        with st.container():
            c1, c2, c3 = st.columns([1, 5, 2])
            
            with c1:
                st.write(f"**{row['Symbol']}**")
                st.caption(row['Date'].strftime('%d-%b'))
            
            with c2:
                # Headline with color coding
                css_class = "positive" if row['Sentiment'] == "Positive" else "negative"
                st.markdown(f'<span class="{css_class}">{row["Headline"]}</span>', unsafe_allow_html=True)
                
                # Details expander
                with st.expander("Read Details"):
                    st.write(row['Details'])
            
            with c3:
                # Deal Value Display
                if row['Value_Cr'] > 0:
                    st.markdown(f'<span class="big-money">₹ {row["Value_Cr"]} Cr</span>', unsafe_allow_html=True)
                else:
                    st.caption("Value not disclosed")
                    
            st.markdown("---")
else:
    st.info("No stocks match your filters. Try lowering the Deal Value or changing the date.")
