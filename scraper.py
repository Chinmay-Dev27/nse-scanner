import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import os
import re
import feedparser

# --- CONFIGURATION ---
DATA_FILE = "nse_data.csv"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.nseindia.com/'
}

def extract_deal_value(text):
    """
    Robust extraction for money formats:
    - "Rs. 654.03 Crores" -> 654.03
    - "Order worth 500 Cr" -> 500.0
    - "3.5 Million" -> 0.35 (Converted to Cr)
    """
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    
    # Pattern 1: Explicit Cr/Crore
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    
    # Pattern 2: Million (1 Million = 0.1 Crore)
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    
    return 0

def fetch_future_events():
    """Fetches Google News for 'L1 Bidder' & 'In Talks' (Future/Rumors)"""
    print("Scanning Future Events...")
    events = []
    
    # Queries for "Potential" news that hasn't been filed yet
    queries = [
        "company L1 bidder project India", 
        "company lowest bidder order", 
        "company in talks acquisition India"
    ]
    
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Top 5 results per query
                events.append({
                    'Date': date.today().strftime('%Y-%m-%d'), # Tagged as today's insight
                    'Symbol': "POTENTIAL NEWS", # Placeholder until user reads headline
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

    # 1. BULK DEALS (Robust Logic)
    print("Fetching Bulk Deals...")
    try:
        # Use 3-day window to avoid "from_date == to_date" error
        end_date = date.today()
        start_date = end_date - timedelta(days=3)
        
        bd = capital_market.bulk_deal_data(from_date=start_date.strftime('%d-%m-%Y'), 
                                           to_date=end_date.strftime('%d-%m-%Y'))
        
        if bd is not None and not bd.empty:
            # --- CRITICAL FIX: Normalize Column Names ---
            bd.columns = [c.strip() for c in bd.columns] # Remove spaces
            rename_map = {
                'Quantity Traded': 'Quantity',
                'Trade Price / Wght. Avg. Price': 'Trade Price'
            }
            bd.rename(columns=rename_map, inplace=True)
            # ---------------------------------------------

            for _, row in bd.iterrows():
                if 'Quantity' in row and 'Trade Price' in row:
                    try:
                        qty = float(str(row['Quantity']).replace(',', ''))
                        price = float(str(row['Trade Price']).replace(',', ''))
                        val = (qty * price) / 10000000 # Convert to Cr
                        
                        all_data.append({
                            'Date': row['Date'],
                            'Symbol': row['Symbol'],
                            'Type': 'Bulk Deal',
                            'Headline': f"Bulk {row['Buy/Sell']}: {row['Quantity']} sh @ ₹{row['Trade Price']}",
                            'Sentiment': 'Positive' if row['Buy/Sell']=='BUY' else 'Negative',
                            'Value_Cr': round(val, 2),
                            'Details': f"Client: {row['Client Name']} | Exchange: NSE"
                        })
                    except:
                        continue
    except Exception as e:
        print(f"Bulk Deal Info: {e}")

    # 2. CORPORATE FILINGS (Official)
    print("Fetching Filings...")
    try:
        from_d = (date.today() - timedelta(days=3)).strftime('%d-%m-%Y')
        to_d = date.today().strftime('%d-%m-%Y')
        
        url = "https://www.nseindia.com/api/corporate-announcements"
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=HEADERS)
        resp = s.get(url, headers=HEADERS, params={'index': 'equities', 'from_date': from_d, 'to_date': to_d})
        
        if resp.status_code == 200:
            for item in resp.json():
                desc = (str(item.get('desc','')) + " " + str(item.get('attchmntText',''))).lower()
                val = extract_deal_value(desc)
                
                # Filter: Keep if Money > 0 OR keywords present
                if val > 0 or any(x in desc for x in ['order', 'contract', 'bagged', 'bonus', 'acquisition', 'dividend']):
                    
                    sent = 'Neutral'
                    if any(x in desc for x in ['order', 'win', 'bagged', 'acquisition']): sent = 'Positive'
                    elif any(x in desc for x in ['penalty', 'fraud', 'default']): sent = 'Negative'

                    all_data.append({
                        'Date': item.get('an_dt'),
                        'Symbol': item.get('symbol'),
                        'Type': 'Official Filing',
                        'Headline': item.get('desc'),
                        'Sentiment': sent,
                        'Value_Cr': val,
                        'Details': desc[:500]
                    })
    except Exception as e:
        print(f"Filing Info: {e}")

    # 3. FUTURE EVENTS
    df_future = fetch_future_events()
    if not df_future.empty:
        all_data.extend(df_future.to_dict('records'))

    # SAVE TO CSV
    if all_data:
        new_df = pd.DataFrame(all_data)
        # Standardize Date Format
        new_df['Date'] = pd.to_datetime(new_df['Date'], dayfirst=True, errors='coerce')
        
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            existing['Date'] = pd.to_datetime(existing['Date'], errors='coerce')
            
            combined = pd.concat([new_df, existing])
            # Deduplicate
            combined = combined.drop_duplicates(subset=['Date', 'Symbol', 'Headline'])
            combined.to_csv(DATA_FILE, index=False)
        else:
            new_df.to_csv(DATA_FILE, index=False)
        print(f"Success. Saved {len(new_df)} items.")
    else:
        print("Scan complete. No new items.")

if __name__ == "__main__":
    scan_market()
