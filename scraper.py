import pandas as pd
import requests
from nselib import capital_market
from datetime import date, timedelta
import os
import re
import feedparser

# --- CONFIGURATION ---
DATA_FILE = "nse_data.csv"

# 1. OFFICIAL FILING KEYWORDS (Confirmed News)
FILING_KEYWORDS = [
    'order', 'contract', 'agreement', 'awarded', 'bagged', 'letter of acceptance', 
    'loa', 'acquisition', 'bonus', 'dividend', 'buyback'
]

# 2. "UPCOMING" DEAL KEYWORDS (Soft News/Rumors)
# "L1" = Lowest Bidder (Likely to win), "In talks" = Potential deal
EXTERNAL_KEYWORDS = ['l1 bidder', 'lowest bidder', 'preferred bidder', 'in talks', 'considering proposal']

# Trusted Domains (to filter out spam news)
TRUSTED_DOMAINS = ['economictimes', 'moneycontrol', 'livemint', 'business-standard', 'financialexpress']

def analyze_sentiment(text):
    text = text.lower()
    if any(k in text for k in ['penalty', 'fraud', 'default', 'resign', 'litigation']):
        return "Negative"
    if any(k in text for k in FILING_KEYWORDS + EXTERNAL_KEYWORDS):
        return "Positive"
    return "Neutral"

def extract_deal_value(text):
    # Extracts "Rs 500 Cr" or "500 Crore"
    match = re.search(r"(?:rs\.?|inr)\s?(\d+(?:\.\d+)?)\s?(?:cr|crore|mn|million|bn|billion)", text.lower().replace(',', ''))
    return float(match.group(1)) if match else 0

def fetch_corporate_announcements():
    """Scrapes official NSE filings"""
    print("Scanning NSE Official Filings...")
    try:
        from_date = (date.today() - timedelta(days=2)).strftime('%d-%m-%Y')
        to_date = date.today().strftime('%d-%m-%Y')
        url = "https://www.nseindia.com/api/corporate-announcements"
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'}
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers)
        response = session.get(url, headers=headers, params={'index': 'equities', 'from_date': from_date, 'to_date': to_date})
        
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def fetch_external_news():
    """Scrapes Google News RSS for 'Order Wins' & 'L1 Bidder' news"""
    print("Scanning External Trusted News...")
    news_items = []
    # Search queries for Indian Market context
    queries = [
        "NSE stock order win",
        "company bag order contract India",
        "company L1 bidder project India"
    ]
    
    for q in queries:
        encoded_q = q.replace(" ", "%20")
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            # Filter 1: Must be from a trusted domain
            if any(domain in entry.link for domain in TRUSTED_DOMAINS):
                # Filter 2: Must happen in last 24 hours
                news_items.append({
                    'Date': date.today().strftime('%Y-%m-%d'),
                    'Symbol': "MARKET NEWS", # We don't know the symbol yet, will extraction in App or here
                    'Type': 'External News (Potential)',
                    'Headline': entry.title,
                    'Sentiment': 'Positive', # Assumed based on query
                    'Value_Cr': extract_deal_value(entry.title),
                    'Details': f"Source: {entry.source.title} | Link: {entry.link}"
                })
    return pd.DataFrame(news_items)

def scan_market():
    clean_news = []
    
    # 1. NSE FILINGS
    df_nse = fetch_corporate_announcements()
    if not df_nse.empty:
        for _, row in df_nse.iterrows():
            subject = (str(row.get('desc', '')) + " " + str(row.get('attchmntText', ''))).lower()
            val = extract_deal_value(subject)
            sent = analyze_sentiment(subject)
            
            if sent != "Neutral" or val > 0:
                clean_news.append({
                    'Date': row.get('an_dt'), # Use ISO format if possible
                    'Symbol': row.get('symbol'),
                    'Type': 'Official Filing',
                    'Headline': row.get('desc'),
                    'Sentiment': sent,
                    'Value_Cr': val,
                    'Details': subject[:500]
                })

    # 2. EXTERNAL NEWS
    df_ext = fetch_external_news()
    if not df_ext.empty:
        # Try to extract Symbol from Headline (Simple heuristic: All Caps words)
        # In a real app, you'd match against a master list of symbols.
        # Here we just append it.
        clean_news.extend(df_ext.to_dict('records'))

    # 3. SAVE
    if clean_news:
        new_df = pd.DataFrame(clean_news)
        if os.path.exists(DATA_FILE):
            existing = pd.read_csv(DATA_FILE)
            pd.concat([new_df, existing]).drop_duplicates(subset=['Headline']).head(500).to_csv(DATA_FILE, index=False)
        else:
            new_df.to_csv(DATA_FILE, index=False)
        print("Data Updated Successfully.")

if __name__ == "__main__":
    scan_market()
