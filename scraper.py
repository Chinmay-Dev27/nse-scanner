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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.nseindia.com/'
}

def extract_deal_value(text):
    """
    Robust extraction for formats like:
    - "Rs. 654.03 Crores"
    - "Order worth 500 Cr"
    - "3.5 Million"
    """
    if not isinstance(text, str): return 0
    text = text.lower().replace(',', '')
    
    # Pattern 1: Explicit "Cr" or "Crore"
    # Matches: "rs 500 cr", "500.50 crores", "INR 500cr"
    match_cr = re.search(r"(?:rs\.?|inr)?\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)", text)
    if match_cr:
        return float(match_cr.group(1))
        
    # Pattern 2: "Million" (Convert to Cr: 1 Million = 0.1 Cr)
    match_mn = re.search(r"(\d+(?:\.\d+)?)\s?(?:mn|million)", text)
    if match_mn:
        return round(float(match_mn.group(1)) * 0.1, 2)
        
    return 0

def fetch_board_meetings():
    """Fetches FUTURE events (Board Meetings)"""
    print("Scanning Upcoming Board Meetings...")
    try:
        url = "https://www.nseindia.com/api/board-meetings"
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=HEADERS)
        response = session.get(url, headers=HEADERS)
        
        if response.status_code == 200:
            data = response.json()
            # Normalize data
            rows = []
            for item in data:
                rows.append({
                    'Date': item.get('meetingdate', date.today().strftime('%d-%b-%Y')), 
                    'Symbol': item.get('symbol'),
                    'Type': 'Future Event',
                    'Headline': f"Board Meeting: {item.get('purpose')}",
                    'Sentiment': 'Neutral', # Agenda determines sentiment, usually Neutral until outcome
                    'Value_Cr': 0,
                    'Details': f"Agenda: {item.get('purpose')}"
                })
            return pd.DataFrame(rows)
    except Exception as e:
        print(f"Board Meeting Error: {e}")
    return pd.DataFrame()

def fetch_corporate_announcements():
    """Fetches PAST/PRESENT official filings"""
    print("Scanning Corporate Filings...")
    try:
        # Fetch last 7 days to ensure we don't miss anything
        from_date = (date.today() - timedelta(days=7)).strftime('%d-%m-%Y')
        to_date = date.today().strftime('%d-%m-%Y')
        
        url = "https://www.nseindia.com/api/corporate-announcements"
        params = {'index': 'equities', 'from_date': from_date, 'to_date': to_date}
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=HEADERS)
        response = session.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        return pd.DataFrame()
    except Exception as e:
        print(f"Filings Error: {e}")
        return pd.DataFrame()

def scan_market():
    all_data = []
    
    # 1. GET PAST/PRESENT NEWS (Filings)
    df_filings = fetch_corporate_announcements()
    if not df_filings.empty:
        for _, row in df_filings.iterrows():
            # Combine subject and details for better regex search
            full_text = f"{row.get('desc', '')} {row.get('attchmntText', '')}"
            val = extract_deal_value(full_text)
            
            # Auto-Sentiment
            sent = "Neutral"
            if val > 0 or any(x in full_text.lower() for x in ['order', 'bagged', 'awarded', 'bonus']):
                sent = "Positive"
            elif 'penalty' in full_text.lower() or 'fraud' in full_text.lower():
                sent = "Negative"
            
            all_data.append({
                'Date': row.get('an_dt'), # 2024-01-13
                'Symbol': row.get('symbol'),
                'Type': 'Official Filing',
                'Headline': row.get('desc'),
                'Sentiment': sent,
                'Value_Cr': val,
                'Details': full_text[:500]
            })

    # 2. GET FUTURE NEWS (Board Meetings)
    df_meetings = fetch_board_meetings()
    if not df_meetings.empty:
        all_data.extend(df_meetings.to_dict('records'))

    # 3. SAVE DATA
    if all_data:
        new_df = pd.DataFrame(all_data)
        # Handle date formatting uniformity
        new_df['Date'] = pd.to_datetime(new_df['Date'], dayfirst=True, errors='coerce')
        
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            existing['Date'] = pd.to_datetime(existing['Date'], errors='coerce')
            combined = pd.concat([new_df, existing]).drop_duplicates(subset=['Date', 'Symbol', 'Headline'])
            combined.to_csv(DATA_FILE, index=False)
        else:
            new_df.to_csv(DATA_FILE, index=False)
        print(f"Saved {len(new_df)} new items.")

if __name__ == "__main__":
    scan_market()
