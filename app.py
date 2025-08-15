import requests
from datetime import datetime
import pytz

# Config
BASE_URL = "https://api.delta.exchange/v2"
IST = pytz.timezone("Asia/Kolkata")
TARGET_STRIKE = 128400

def fetch_products():
    """Fetch all BTC option products."""
    r = requests.get(f"{BASE_URL}/products")
    r.raise_for_status()
    products = r.json().get("result", [])
    return [p for p in products if p.get("symbol", "").startswith(("C-BTC", "P-BTC"))]

def fetch_ticker(symbol):
    """Fetch ticker details for given symbol."""
    r = requests.get(f"{BASE_URL}/tickers/{symbol}")
    r.raise_for_status()
    return r.json().get("result", {})

def get_strike_data():
    products = fetch_products()
    target_products = [p for p in products if float(p["strike_price"]) == TARGET_STRIKE]

    if not target_products:
        print(f"No products found for strike {TARGET_STRIKE}")
        return
    
    print(f"📅 Data Time: {datetime.now(IST).strftime('%d-%m-%Y %I:%M:%S %p IST')}")
    
    for prod in target_products:
        data = fetch_ticker(prod["symbol"])
        quotes = data.get("quotes", {})
        
        bid = float(quotes["best_bid"]) if quotes.get("best_bid") else None
        ask = float(quotes["best_ask"]) if quotes.get("best_ask") else None
        mid_price = round((bid + ask) / 2, 2) if bid and ask else None
        
        print(f"Symbol: {prod['symbol']}")
        print(f" Strike: {TARGET_STRIKE}")
        print(f" Bid Price: {bid}")
        print(f" Ask Price: {ask}")
        print(f" Mark Price: {data.get('mark_price')}")
        print(f" Mid Price: {mid_price}")
        print(f" OI (Contracts): {data.get('oi_contracts')}")
        print(f" Delta: {data.get('greeks', {}).get('delta')}")
        print("-" * 40)

if __name__ == "__main__":
    get_strike_data()
