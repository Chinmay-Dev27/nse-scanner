import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import os
import re
import feedparser
import time

# --- CONFIG ---
DATA_FILE = "nse_data.csv"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def extract_deal_value(text):
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    # Match Cr/Crore
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    # Match Million (convert to Cr)
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    return 0

def clean_symbol(sym):
    if not isinstance(sym, str): return "UNKNOWN"
    return sym.strip().replace(" ", "").upper()

def fetch_future_events():
    print("Scanning Future Events...")
    events = []
    # BROADENED QUERIES to ensure hits
    queries = [
        "company L1 bidder project India", 
        "company lowest bidder order", 
        "company bag order contract India",
        "company in talks acquisition India",
        "merger discussions India company",
        "company stake sale India",
        "NSE listed company new order"
    ]
    
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            # Take top 2 from each query to avoid spam
            for entry in feed.entries[:2]:
                events.append({
                    'Date': date.today().strftime('%Y-%m-%d'),
                    'Symbol': "POTENTIAL NEWS",
                    'Type': 'Future/Rumor',
                    'Headline': entry.title,
                    'Sentiment': 'Positive',
                    'Value_Cr': extract_deal_value(entry.title),
                    'Details': f"Source: {entry.source.title} | Link: {entry.link}"
                })
        except: continue
    
    # Remove duplicates based on headline
    df = pd.DataFrame(events)
    if not df.empty:
        df = df.drop_duplicates(subset=['Headline'])
    return df

def fetch_bulk_deals_robust():
    """Fetches Bulk Deals in small chunks to avoid API failure"""
    print("Fetching Bulk Deals (Chunked)...")
    all_deals = []
    
    # Scan last 15 days in 3-day chunks (Reliable method)
    for i in range(0, 15, 3):
        try:
            end = date.today() - timedelta(days=i)
            start = end - timedelta(days=2)
            
            # Skip if start date is in future (edge case)
            if start > date.today(): continue

            bd = capital_market.bulk_deal_data(from_date=start.strftime('%d-%m-%Y'), 
                                               to_date=end.strftime('%d-%m-%Y'))
            
            if bd is not None and not bd.empty:
                bd.columns = [c.strip() for c in bd.columns]
                bd.rename(columns={'Quantity Traded': 'Quantity', 'Trade Price / Wght. Avg. Price': 'Trade Price'}, inplace=True)
                
                for _, row in bd.iterrows():
                    if 'Quantity' in row:
                        qty = float(str(row['Quantity']).replace(',', ''))
                        price = float(str(row['Trade Price']).replace(',', ''))
                        val = (qty * price) / 10000000
                        
                        all_deals.append({
                            'Date': row['Date'], 
                            'Symbol': clean_symbol(row['Symbol']), 
                            'Type': 'Bulk Deal',
                            'Headline': f"Bulk {row['Buy/Sell']}: {qty:,.0f} sh @ ₹{price:.2f}",
                            'Sentiment': 'Positive' if row['Buy/Sell']=='BUY' else 'Negative',
                            'Value_Cr': round(val, 2), 
                            'Details': f"Client: {row['Client Name']}"
                        })
            time.sleep(0.5) # Polite delay
        except Exception as e:
            print(f"Chunk failed: {e}")
            continue
            
    return pd.DataFrame(all_deals)

def scan_market():
    all_data = []

    # 1. BULK DEALS (New Robust Function)
    df_bd = fetch_bulk_deals_robust()
    if not df_bd.empty:
        all_data.extend(df_bd.to_dict('records'))

    # 2. OFFICIAL FILINGS
    print("Fetching Filings...")
    try:
        from_d = (date.today() - timedelta(days=5)).strftime('%d-%m-%Y')
        to_d = date.today().strftime('%d-%m-%Y')
        url = "https://www.nseindia.com/api/corporate-announcements"
        s = requests.Session(); s.get("https://www.nseindia.com", headers=HEADERS)
        resp = s.get(url, headers=HEADERS, params={'index': 'equities', 'from_date': from_d, 'to_date': to_d})
        
        if resp.status_code == 200:
            for item in resp.json():
                desc = (str(item.get('desc','')) + " " + str(item.get('attchmntText',''))).lower()
                val = extract_deal_value(desc)
                if val > 0 or any(x in desc for x in ['order', 'contract', 'bagged', 'bonus', 'acquisition']):
                    all_data.append({
                        'Date': item.get('an_dt'), 
                        'Symbol': clean_symbol(item.get('symbol')), 
                        'Type': 'Official Filing',
                        'Headline': item.get('desc'),
                        'Sentiment': 'Positive' if 'order' in desc else 'Neutral',
                        'Value_Cr': val, 
                        'Details': desc[:500]
                    })
    except Exception as e: print(f"Filing Err: {e}")

    # 3. FUTURE EVENTS
    df_future = fetch_future_events()
    if not df_future.empty: all_data.extend(df_future.to_dict('records'))

    # SAVE
    if all_data:
        new_df = pd.DataFrame(all_data)
        new_df['Date'] = pd.to_datetime(new_df['Date'], dayfirst=True, errors='coerce')
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            existing['Date'] = pd.to_datetime(existing['Date'], errors='coerce')
            combined = pd.concat([new_df, existing]).drop_duplicates(subset=['Date', 'Symbol', 'Headline'])
            combined.to_csv(DATA_FILE, index=False)
        else: new_df.to_csv(DATA_FILE, index=False)
        print(f"Saved {len(new_df)} items.")

if __name__ == "__main__":
    scan_market()
