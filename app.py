import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"
IST = pytz.timezone("Asia/Kolkata")

# ======================
# UTILS
# ======================
def fetch_products():
    """Fetch all products from Delta Exchange."""
    r = requests.get(f"{BASE_URL}/products")
    r.raise_for_status()
    return r.json().get("result", [])

def filter_btc_options(products):
    """Return only BTC options contracts."""
    return [p for p in products if p.get("symbol", "").startswith(("C-BTC", "P-BTC"))]

def get_nearest_expiry():
    """Find nearest expiry and its products."""
    products = filter_btc_options(fetch_products())
    if not products:
        return None, []
    expiry_dates = sorted(set(p["settlement_time"] for p in products))
    if not expiry_dates:
        return None, []
    nearest_expiry_str = expiry_dates[0]
    nearest_expiry_dt = datetime.fromisoformat(nearest_expiry_str.replace("Z", "+00:00")).astimezone(IST)
    nearest_expiry_products = [p for p in products if p["settlement_time"] == nearest_expiry_str]
    return nearest_expiry_dt, nearest_expiry_products

def fetch_ticker(symbol):
    """Fetch mid-price for an option symbol."""
    url = f"{BASE_URL}/tickers/{symbol}"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json().get("result", {})
    quotes = data.get("quotes", {})
    bid = quotes.get("best_bid")
    ask = quotes.get("best_ask")
    if bid is None or ask is None:
        return None
    try:
        return (float(bid) + float(ask)) / 2
    except ValueError:
        return None

# ======================
# STREAMLIT UI
# ======================
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("₿ BTC Options Chain Viewer")

expiry_datetime, products = get_nearest_expiry()
if expiry_datetime is None or not products:
    st.error("Could not fetch nearest expiry.")
    st.stop()

st.subheader(f"Nearest Expiry: {expiry_datetime.strftime('%d %b %Y %I:%M %p IST')}")

calls = []
puts = []

for p in products:
    symbol = p["symbol"]
    strike = float(p["strike_price"])
    mid = fetch_ticker(symbol)
    if mid is None:
        continue
    if symbol.startswith("C-BTC"):
        calls.append({"Strike": strike, "Call Mid Price": mid})
    elif symbol.startswith("P-BTC"):
        puts.append({"Strike": strike, "Put Mid Price": mid})

df_calls = pd.DataFrame(calls).sort_values(by="Strike")
df_puts = pd.DataFrame(puts).sort_values(by="Strike")
df = pd.merge(df_calls, df_puts, on="Strike", how="outer").sort_values(by="Strike").reset_index(drop=True)

st.dataframe(df, use_container_width=True)
