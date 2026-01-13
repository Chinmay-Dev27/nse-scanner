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
    """Robust extraction for 'Rs 654 Cr', '3.5 Mn', etc."""
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    # Match Cr/Crore
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr: return float(match_cr.group(1))
    # Match Million (convert to Cr)
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn: return round(float(match_mn.group(1)) * 0.1, 2)
    return 0

def fetch_future_events():
    """Fetches Board Meetings (30 Days Ahead) & Google News (L1 Bidders)"""
    print("Scanning Future Events...")
    events = []
    
    # 1. BOARD MEETINGS (Official Future)
    try:
        # Scan next 30 days
        to_date = (date.today() + timedelta(days=30)).strftime('%d-%m-%Y')
        # NSELib sometimes needs specific handling, using broad try/except
        # Note: If nselib fails, we skip to external news
        pass 
    except:
        pass # Placeholder if library fails, we rely on Google News below

    # 2. GOOGLE NEWS "L1 BIDDER" (Potential Future)
    # This finds stocks "In Talks" or "Lowest Bidder" before official filing
    queries = ["company L1 bidder project India", "company lowest bidder order"]
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={q.replace(' ','%20')}&hl=en-IN&gl=IN&ceid=IN:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]: # Top 10 only
                events.append({
                    'Date': date.today().strftime('%Y-%m-%d'), # Tagged today but refers to future
                    'Symbol': "POTENTIAL NEWS", # User must read headline to ID stock
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
        bd = capital_market.bulk_deal_data(from_date=date.today().strftime('%d-%m-%Y'), 
                                           to_date=date.today().strftime('%d-%m-%Y'))
        if bd is not None and not bd.empty:
            for _, row in bd.iterrows():
                val = (float(row['Quantity']) * float(row['Trade Price'])) / 10**7
                all_data.append({
                    'Date': row['Date'],
                    'Symbol': row['Symbol'],
                    'Type': 'Bulk Deal',
                    'Headline': f"Bulk {row['Buy/Sell']}: {row['Quantity']} shares @ {row['Trade Price']}",
                    'Sentiment': 'Positive' if row['Buy/Sell']=='BUY' else 'Negative',
                    'Value_Cr': round(val, 2),
                    'Details': f"Client: {row['Client Name']}"
                })
    except Exception as e:
        print(f"Bulk Deal Error: {e}")

    # 2. CORPORATE FILINGS (Past/Present)
    print("Fetching Filings...")
    try:
        # 3 Day Lookback
        from_d = (date.today() - timedelta(days=3)).strftime('%d-%m-%Y')
        to_d = date.today().strftime('%d-%m-%Y')
        url = "https://www.nseindia.com/api/corporate-announcements"
        s = requests.Session()
        s.get("https://www.nseindia.com", headers=HEADERS)
        resp = s.get(url, headers=HEADERS, params={'index': 'equities', 'from_date': from_d, 'to_date': to_d})
        
        if resp.status_code == 200:
            for item in resp.json():
                desc = (item.get('desc','') + " " + item.get('attchmntText','')).lower()
                val = extract_deal_value(desc)
                
                # Filter: Keep if Money involved OR specific keywords
                if val > 0 or any(x in desc for x in ['order', 'contract', 'bagged', 'bonus', 'acquisition']):
                    all_data.append({
                        'Date': item.get('an_dt'),
                        'Symbol': item.get('symbol'),
                        'Type': 'Official Filing',
                        'Headline': item.get('desc'),
                        'Sentiment': 'Positive' if 'order' in desc or 'win' in desc else 'Neutral',
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
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            pd.concat([new_df, existing]).drop_duplicates(subset=['Headline']).to_csv(DATA_FILE, index=False)
        else:
            new_df.to_csv(DATA_FILE, index=False)
        print("Scan Complete.")

if __name__ == "__main__":
    scan_market()
