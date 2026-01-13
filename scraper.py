import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import time
import os

# --- CONFIGURATION ---
# Keywords that suggest a new order or contract
POSITIVE_KEYWORDS = [
    'order', 'contract', 'agreement', 'awarded', 'bagged', 
    'letter of acceptance', 'loa', 'mou', 'partnership', 'acquisition'
]

# File to store data
DATA_FILE = "nse_data.csv"

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/'
    }

def fetch_corporate_announcements():
    """
    Fetches the latest corporate announcements from NSE.
    Note: Using direct NSE API with headers to ensure 'authentic' data.
    """
    print("Fetching Corporate Announcements...")
    try:
        # NSE allows fetching announcements for the last few days
        # We look back 2 days to ensure we don't miss anything over weekends
        from_date = (date.today() - timedelta(days=2)).strftime('%d-%m-%Y')
        to_date = date.today().strftime('%d-%m-%Y')
        
        # This is a public NSE endpoint for announcements
        url = "https://www.nseindia.com/api/corporate-announcements"
        params = {
            'index': 'equities',
            'from_date': from_date,
            'to_date': to_date
        }
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=get_headers()) # Visit home to get cookies
        response = session.get(url, headers=get_headers(), params=params)
        
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)
        else:
            print(f"Failed to fetch announcements. Status: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"Error fetching announcements: {e}")
        return pd.DataFrame()

def scan_market():
    # 1. FETCH ANNOUNCEMENTS
    df_announcements = fetch_corporate_announcements()
    
    clean_news = []
    
    if not df_announcements.empty:
        # Filter for relevant keywords
        for index, row in df_announcements.iterrows():
            subject = str(row.get('desc', '')).lower() + " " + str(row.get('attchmntText', '')).lower()
            
            # Check if any keyword exists in the subject
            found_keywords = [kw for kw in POSITIVE_KEYWORDS if kw in subject]
            
            if found_keywords:
                clean_news.append({
                    'Date': row.get('an_dt'),
                    'Symbol': row.get('symbol'),
                    'Type': 'Contract/Order News',
                    'Description': row.get('desc'),
                    'Source': 'NSE Corporate Filings',
                    'Sentiment': 'Positive'
                })

    # 2. FETCH BULK DEALS (FII/DII)
    print("Fetching Bulk Deals...")
    try:
        # Fetching bulk deals for today
        deals = capital_market.bulk_deal_data(from_date=date.today().strftime('%d-%m-%Y'), 
                                              to_date=date.today().strftime('%d-%m-%Y'))
        
        if deals is not None and not deals.empty:
            for index, row in deals.iterrows():
                # We are interested in BUY orders
                if row['Buy/Sell'] == 'BUY':
                    clean_news.append({
                        'Date': row['Date'],
                        'Symbol': row['Symbol'],
                        'Type': 'Bulk Deal (BUY)',
                        'Description': f"Bought {row['Quantity']} shares at {row['Trade Price']}",
                        'Source': f"Client: {row['Client Name']}",
                        'Sentiment': 'Neutral/Positive'
                    })
    except Exception as e:
        print(f"Error fetching bulk deals: {e}")

    # 3. SAVE DATA
    new_df = pd.DataFrame(clean_news)
    
    # If file exists, append; otherwise create new
    if os.path.exists(DATA_FILE):
        existing_df = pd.read_csv(DATA_FILE)
        # Combine and remove duplicates
        combined_df = pd.concat([new_df, existing_df]).drop_duplicates(subset=['Date', 'Symbol', 'Description'])
        # Keep only last 30 days of data to keep it fast
        combined_df = combined_df.head(1000) 
        combined_df.to_csv(DATA_FILE, index=False)
    else:
        new_df.to_csv(DATA_FILE, index=False)
        
    print("Scan complete. Data updated.")

if __name__ == "__main__":
    scan_market()
