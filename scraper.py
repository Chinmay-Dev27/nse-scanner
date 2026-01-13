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
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def extract_deal_value(text):
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    return 0

def clean_symbol(sym):
    if not isinstance(sym, str): return "UNKNOWN"
    return sym.strip().replace(" ", "").upper()

def fetch_future_events():
    print("Scanning Future Events & Rumors...")
    events = []
    # BROADENED QUERIES (As per your request)
    queries = [
        "Order win", 
        "Acquisition", 
        "Stake sale", 
        "company bag order contract India",
        "company lowest bidder order",
        "merger talks India",
        "share buyback India",
        "bonus issue India"
    ]
    
    for q in queries:
        try:
            # Search Google News RSS
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            
            # Take Top 2 entries per query to prevent overload
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
    
    # Deduplicate by Headline
    if events:
        df = pd.DataFrame(events)
        df = df.drop_duplicates(subset=['Headline'])
        return df
    return pd.DataFrame(events)

def fetch_bulk_deals_robust():
    """
    Fetches Bulk Deals Day-by-Day.
    This is slower but fixes the 'Empty Data' API error.
    """
    print("Fetching Bulk Deals (Day-by-Day Loop)...")
    all_deals = []
    
    # Scan last 7 days individually
    for i in range(7):
        target_date = date.today() - timedelta(days=i)
        date_str = target_date.strftime('%d-%m-%Y')
        
        try:
            # Request specific day only
            bd = capital_market.bulk_deal_data(from_date=date_str, to_date=date_str)
            
            if bd is not None and not bd.empty:
                # Normalize Columns
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
            time.sleep(0.5) # Prevent Rate Limiting
            
        except Exception:
            # If one day fails (e.g., Weekend), just skip to next
            continue
            
    return pd.DataFrame(all_deals)

def scan_market():
    all_data = []

    # 1. BULK DEALS (Updated Logic)
    df_bd = fetch_bulk_deals_robust()
    if not df_bd.empty:
        all_data.extend(df_bd.to_dict('records'))

    # 2. OFFICIAL FILINGS
    print("Fetching Filings...")
    try:
        from_d = (date.today() - timedelta(days=3)).strftime('%d-%m-%Y')
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

    # 3. FUTURE EVENTS (Updated Logic)
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
