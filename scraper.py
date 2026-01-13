import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import os
import re
import feedparser

# --- CONFIG ---
DATA_FILE = "nse_data.csv"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def extract_deal_value(text):
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    return 0

def fetch_future_events():
    """Scans Google News for rumors/upcoming deals"""
    print("Scanning Future Events...")
    events = []
    # Broadened queries to ensure data
    queries = [
        "company L1 bidder project India", 
        "company lowest bidder order", 
        "company bag order contract India",
        "company in talks acquisition India"
    ]
    
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            # Take top 3 from each query
            for entry in feed.entries[:3]:
                events.append({
                    'Date': date.today().strftime('%Y-%m-%d'),
                    'Symbol': "POTENTIAL NEWS", # Explicit tag for App to recognize
                    'Type': 'Future/Rumor',
                    'Headline': entry.title,
                    'Sentiment': 'Positive',
                    'Value_Cr': extract_deal_value(entry.title),
                    'Details': f"Source: {entry.source.title} | Link: {entry.link}"
                })
        except:
            continue
    return pd.DataFrame(events)

def scan_market():
    all_data = []

    # 1. BULK DEALS
    print("Fetching Bulk Deals...")
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=3)
        bd = capital_market.bulk_deal_data(from_date=start_date.strftime('%d-%m-%Y'), 
                                           to_date=end_date.strftime('%d-%m-%Y'))
        if bd is not None and not bd.empty:
            bd.columns = [c.strip() for c in bd.columns]
            bd.rename(columns={'Quantity Traded': 'Quantity', 'Trade Price / Wght. Avg. Price': 'Trade Price'}, inplace=True)
            
            for _, row in bd.iterrows():
                if 'Quantity' in row:
                    try:
                        qty = float(str(row['Quantity']).replace(',', ''))
                        price = float(str(row['Trade Price']).replace(',', ''))
                        val = (qty * price) / 10000000
                        all_data.append({
                            'Date': row['Date'], 'Symbol': row['Symbol'], 'Type': 'Bulk Deal',
                            'Headline': f"Bulk {row['Buy/Sell']}: {qty:.0f} sh @ {price}",
                            'Sentiment': 'Positive' if row['Buy/Sell']=='BUY' else 'Negative',
                            'Value_Cr': round(val, 2), 'Details': f"Client: {row['Client Name']}"
                        })
                    except: continue
    except Exception as e: print(f"Bulk Deal Err: {e}")

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
                        'Date': item.get('an_dt'), 'Symbol': item.get('symbol'), 'Type': 'Official Filing',
                        'Headline': item.get('desc'),
                        'Sentiment': 'Positive' if 'order' in desc else 'Neutral',
                        'Value_Cr': val, 'Details': desc[:500]
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
