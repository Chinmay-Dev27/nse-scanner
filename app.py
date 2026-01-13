import streamlit as st
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(
    page_title="NSE Authentic News Scanner",
    layout="wide",
    page_icon="📈"
)

# --- TITLE & STYLE ---
st.title("📈 NSE Authentic News & Contract Scanner")
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6
    }
    .big-font {
        font-size:20px !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.write("This tool scans **official NSE Corporate Filings** for keywords (Contracts, Orders, LoA) and **Bulk Deals**.")

# --- LOAD DATA ---
try:
    df = pd.read_csv("nse_data.csv")
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
    df = df.sort_values(by='Date', ascending=False)
except FileNotFoundError:
    st.warning("No data found yet. Please wait for the daily scan to run.")
    df = pd.DataFrame(columns=['Date', 'Symbol', 'Type', 'Description', 'Source', 'Sentiment'])

# --- SIDEBAR SEARCH ---
st.sidebar.header("🔍 Filter Options")

# Search by Symbol
symbol_list = ['All'] + sorted(df['Symbol'].unique().tolist())
selected_symbol = st.sidebar.selectbox("Select Stock Symbol", symbol_list)

# Search by Type
type_list = ['All'] + sorted(df['Type'].unique().tolist())
selected_type = st.sidebar.selectbox("Select News Type", type_list)

# Search by Keyword
search_query = st.sidebar.text_input("Search keywords (e.g., 'Solar', 'Defense')")

# --- FILTERING LOGIC ---
filtered_df = df.copy()

if selected_symbol != 'All':
    filtered_df = filtered_df[filtered_df['Symbol'] == selected_symbol]

if selected_type != 'All':
    filtered_df = filtered_df[filtered_df['Type'] == selected_type]

if search_query:
    filtered_df = filtered_df[filtered_df['Description'].str.contains(search_query, case=False, na=False)]

# --- MAIN DISPLAY ---

# Metrics Row
col1, col2, col3 = st.columns(3)
col1.metric("Total News Found", len(filtered_df))
col2.metric("Contract/Order News", len(filtered_df[filtered_df['Type'] == 'Contract/Order News']))
col3.metric("Bulk Deals (Buy)", len(filtered_df[filtered_df['Type'] == 'Bulk Deal (BUY)']))

st.divider()

# Results Table
if not filtered_df.empty:
    st.subheader("📋 Latest Findings")
    
    # Iterate to make it look like a news feed
    for index, row in filtered_df.iterrows():
        with st.container():
            c1, c2 = st.columns([1, 4])
            with c1:
                st.info(f"**{row['Symbol']}**\n\n{row['Date'].strftime('%d-%b-%Y')}")
            with c2:
                if "Contract" in row['Type']:
                    st.success(f"**{row['Type']}**")
                else:
                    st.warning(f"**{row['Type']}**")
                
                st.write(f"**Details:** {row['Description']}")
                st.caption(f"Source: {row['Source']}")
            st.markdown("---")
else:
    st.info("No news found matching your criteria.")

# --- AUTO REFRESH NOTE ---
st.sidebar.markdown("---")
st.sidebar.caption("Data is auto-updated daily via GitHub Actions.")

