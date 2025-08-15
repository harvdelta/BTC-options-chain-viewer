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

def fetch_ticker_details(symbol):
    """Fetch detailed data for a given option symbol."""
    r = requests.get(f"{BASE_URL}/tickers/{symbol}")
    r.raise_for_status()
    data = r.json().get("result", {})
    quotes = data.get("quotes", {})

    return {
        "symbol": symbol,
        "best_bid": quotes.get("best_bid"),
        "best_ask": quotes.get("best_ask"),
        "mark_price": data.get("mark_price"),
        "oi_contracts": data.get("oi_contracts"),
        "oi_value_usd": data.get("oi_value_usd"),
        "delta": data.get("greeks", {}).get("delta"),
        "gamma": data.get("greeks", {}).get("gamma"),
        "vega": data.get("greeks", {}).get("vega"),
        "theta": data.get("greeks", {}).get("theta"),
    }

# Main test
products = fetch_products()
target_products = [p for p in products if float(p["strike_price"]) == TARGET_STRIKE]

if not target_products:
    print(f"No product found for strike {TARGET_STRIKE}")
else:
    print(f"Data as of: {datetime.now(IST).strftime('%d %b %Y %I:%M:%S %p IST')}")
    for prod in target_products:
        details = fetch_ticker_details(prod["symbol"])
        print(details)
