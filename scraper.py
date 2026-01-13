import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import os
import re
import feedparser

# --- CONFIG ---
DATA_FILE = "nse_data.csv"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.nseindia.com/'
}

def extract_deal_value(text):
    """Robust extraction for 'Rs 654 Cr', '3.5 Mn', etc."""
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    
    # Match Cr/Crore (e.g., "Rs 500 Cr", "500.50 Crores")
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    
    # Match Million (convert to Cr, e.g., "10 Million" -> 1 Cr)
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    
    return 0

def fetch_future_events():
    """Fetches Google News for 'L1 Bidder' (Potential Wins)"""
    print("Scanning Future Events...")
    events = []
    
    # 1. GOOGLE NEWS "L1 BIDDER"
    queries = ["company L1 bidder project India", "company lowest bidder order", "company in talks acquisition India"]
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Top 5 per query
                events.append({
                    'Date': date.today().strftime('%Y-%m-%d'),
                    'Symbol': "POTENTIAL NEWS",
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

    # 1. BULK DEALS (FIXED: Uses 3-day range to avoid 'from=to' error)
    print("Fetching Bulk Deals...")
    try:
        # Look back 3 days to ensure valid range and catch recent data
        end_date = date.today()
        start_date = end_date - timedelta(days=3)
        
        bd = capital_market.bulk_deal_data(from_date=start_date.strftime('%d-%m-%Y'), 
                                           to_date=end_date.strftime('%d-%m-%Y'))
        
        if bd is not None and not bd.empty:
            for _, row in bd.iterrows():
                # Calculate Deal Value in Cr
                qty = float(str(row['Quantity']).replace(',', ''))
                price = float(str(row['Trade Price']).replace(',', ''))
                val = (qty * price) / 10000000 # Convert to Crores
                
                all_data.append({
                    'Date': row['Date'],
                    'Symbol': row['Symbol'],
                    'Type': 'Bulk Deal',
                    'Headline': f"Bulk {row['Buy/Sell']}: {row['Quantity']} sh @ ₹{row['Trade Price']}",
                    'Sentiment': 'Positive' if row['Buy/Sell']=='BUY' else 'Negative',
                    'Value_Cr': round(val, 2),
                    'Details': f"Client: {row['Client Name']} | Exchange: NSE"
                })
    except Exception as e:
        print(f"Bulk Deal Error (Ignored): {e}")

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
                
                # Filter: Keep if Money > 0 OR key words present
                if val > 0 or any(x in desc for x in ['order', 'contract', 'bagged', 'bonus', 'acquisition', 'dividend']):
                    # Determine Sentiment
                    sent = 'Neutral'
                    if any(x in desc for x in ['order', 'win', 'bagged', 'acquisition']): sent = 'Positive'
                    elif any(x in desc for x in ['penalty', 'fraud', 'default']): sent = 'Negative'

                    all_data.append({
                        'Date': item.get('an_dt'), # 2024-01-13
                        'Symbol': item.get('symbol'),
                        'Type': 'Official Filing',
                        'Headline': item.get('desc'),
                        'Sentiment': sent,
                        'Value_Cr': val,
                        'Details': desc[:500]
                    })
    except Exception as e:
        print(f"Filing Error: {e}")

    # 3. FUTURE EVENTS
    df_future = fetch_future_events()
    if not df_future.empty:
        all_data.extend(df_future.to_dict('records'))

    # SAVE
    if all_data:
        new_df = pd.DataFrame(all_data)
        # Ensure Date format is consistent for sorting
        new_df['Date'] = pd.to_datetime(new_df['Date'], dayfirst=True, errors='coerce')
        
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            existing['Date'] = pd.to_datetime(existing['Date'], errors='coerce')
            
            # Combine and remove duplicates
            combined = pd.concat([new_df, existing])
            combined = combined.drop_duplicates(subset=['Date', 'Symbol', 'Headline'])
            combined.to_csv(DATA_FILE, index=False)
        else:
            new_df.to_csv(DATA_FILE, index=False)
        print(f"Scan Complete. Saved {len(new_df)} items.")
    else:
        print("Scan Complete. No relevant news found.")

if __name__ == "__main__":
    scan_market()
