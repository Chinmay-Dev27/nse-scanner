import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta, datetime
import os
import re

# --- CONFIGURATION ---
DATA_FILE = "nse_data.csv"

# Keywords to classify news
POSITIVE_KEYWORDS = [
    'order', 'contract', 'awarded', 'bagged', 'letter of acceptance', 'loa', 
    'acquisition', 'partnership', 'bonus', 'dividend', 'buyback', 'winning'
]
NEGATIVE_KEYWORDS = [
    'penalty', 'fine', 'fraud', 'default', 'resignation', 'show cause', 
    'litigation', 'downgrade', 'reject', 'loss'
]

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.nseindia.com/'
    }

def extract_deal_value(text):
    """
    Attempts to extract a monetary value (in Crores) from the text for sorting.
    Returns 0 if no value found.
    """
    text = text.lower().replace(',', '')
    # Regex for "Rs. 100 Crore" or "100 Cr" or "100 Mn"
    # Matches: Rs. 500.50 Crore, 500 Cr, INR 500 Cr
    pattern = r"(?:rs\.?|inr)\s?(\d+(?:\.\d+)?)\s?(?:cr|crore)"
    match = re.search(pattern, text)
    if match:
        try:
            return float(match.group(1))
        except:
            return 0
    return 0

def analyze_sentiment(text):
    text = text.lower()
    if any(k in text for k in NEGATIVE_KEYWORDS):
        return "Negative"
    if any(k in text for k in POSITIVE_KEYWORDS):
        return "Positive"
    return "Neutral"

def fetch_corporate_announcements():
    print("Fetching Corporate Announcements...")
    try:
        # Scan last 3 days to be safe
        from_date = (date.today() - timedelta(days=3)).strftime('%d-%m-%Y')
        to_date = date.today().strftime('%d-%m-%Y')
        
        url = "https://www.nseindia.com/api/corporate-announcements"
        params = {'index': 'equities', 'from_date': from_date, 'to_date': to_date}
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=get_headers())
        response = session.get(url, headers=get_headers(), params=params)
        
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        return pd.DataFrame()
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()

def scan_market():
    clean_news = []
    
    # 1. PROCESS ANNOUNCEMENTS
    df = fetch_corporate_announcements()
    if not df.empty:
        for _, row in df.iterrows():
            subject = str(row.get('desc', '')) + " " + str(row.get('attchmntText', ''))
            
            sentiment = analyze_sentiment(subject)
            deal_value = extract_deal_value(subject)
            
            # FILTER LOGIC: Keep if it has a deal value OR is definitely Positive/Negative
            # Discard generic "Neutral" updates without money
            if sentiment != "Neutral" or deal_value > 0:
                clean_news.append({
                    'Date': row.get('an_dt'), # Format: 2024-01-13
                    'Symbol': row.get('symbol'),
                    'Type': 'Corporate Action',
                    'Headline': row.get('desc'), # Short headline
                    'Sentiment': sentiment,
                    'Value_Cr': deal_value, # Numeric for sorting
                    'Details': subject[:300] + "..." # Truncate for display
                })

    # 2. PROCESS BULK DEALS (Existing logic is fine, just map to new columns)
    try:
        deals = capital_market.bulk_deal_data(from_date=date.today().strftime('%d-%m-%Y'), 
                                              to_date=date.today().strftime('%d-%m-%Y'))
        if deals is not None and not deals.empty:
            for _, row in deals.iterrows():
                # Value calculation: Quantity * Price / 1 Crore
                val_cr = (float(row['Quantity']) * float(row['Trade Price'])) / 10000000
                sentiment = "Positive" if row['Buy/Sell'] == 'BUY' else "Negative"
                
                clean_news.append({
                    'Date': row['Date'], # Ensure date format matches
                    'Symbol': row['Symbol'],
                    'Type': 'Bulk Deal',
                    'Headline': f"Bulk {row['Buy/Sell']} by {row['Client Name']}",
                    'Sentiment': sentiment,
                    'Value_Cr': round(val_cr, 2),
                    'Details': f"Price: {row['Trade Price']}, Qty: {row['Quantity']}"
                })
    except:
        pass

    # 3. SAVE & MERGE
    new_df = pd.DataFrame(clean_news)
    
    if os.path.exists(DATA_FILE):
        existing_df = pd.read_csv(DATA_FILE)
        combined = pd.concat([new_df, existing_df])
        # Deduplicate based on Symbol and Headline
        combined = combined.drop_duplicates(subset=['Date', 'Symbol', 'Headline'])
        # Keep only last 60 days
        combined.to_csv(DATA_FILE, index=False)
    else:
        new_df.to_csv(DATA_FILE, index=False)

if __name__ == "__main__":
    scan_market()
