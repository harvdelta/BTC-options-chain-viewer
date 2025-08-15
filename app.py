import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

BASE_URL = "https://api.delta.exchange"

# ----------- Fetch all products -----------
def fetch_products():
    url = f"{BASE_URL}/v2/products"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("result", [])

# ----------- Fetch best bid/ask and mid price -----------
def fetch_orderbook(symbol):
    url = f"{BASE_URL}/v2/l2orderbook/{symbol}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json().get("result", {})

    buy_book = data.get("buy_book", [])
    sell_book = data.get("sell_book", [])

    best_bid = buy_book[0]["price"] if buy_book else None
    best_ask = sell_book[0]["price"] if sell_book else None

    if best_bid is not None and best_ask is not None:
        return round((best_bid + best_ask) / 2, 1)
    return None

# ----------- Find nearest expiry -----------
def get_nearest_expiry(options):
    now_utc = datetime.now(timezone.utc)  # aware datetime
    future_options = []

    for p in options:
        expiry = datetime.fromisoformat(p["settlement_time"].replace("Z", "+00:00"))
        if expiry > now_utc:
            future_options.append(p)

    if not future_options:
        return None, []

    nearest_expiry = min(
        set([o["settlement_time"] for o in future_options]),
        key=lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    )

    nearest_options = [p for p in future_options if p["settlement_time"] == nearest_expiry]
    return nearest_expiry, nearest_options

# ----------- Streamlit UI -----------
st.set_page_config(page_title="₿ BTC Options Chain Viewer", layout="wide")
st.title("₿ BTC Options Chain Viewer")

# Fetch products
products = fetch_products()

# Filter BTC options only
btc_options = [p for p in products if ("C-BTC" in p["symbol"] or "P-BTC" in p["symbol"])]

# Get nearest expiry
expiry_str, nearest_options = get_nearest_expiry(btc_options)

if not nearest_options:
    st.error("Could not fetch nearest expiry.")
else:
    # Convert expiry to IST
    expiry_dt_utc = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
    expiry_dt_ist = expiry_dt_utc + timedelta(hours=5, minutes=30)
    st.subheader(f"Nearest Expiry: {expiry_dt_ist.strftime('%d-%b-%Y %I:%M %p IST')}")

    # Build data
    data = []
    for opt in nearest_options:
        strike = opt["strike_price"]
        opt_type = "C" if opt["option_type"] == "call" else "P"
        mid_price = fetch_orderbook(opt["symbol"])
        data.append({"type": opt_type, "strike": strike, "mid": mid_price})

    # Convert to DataFrame
    df_calls = pd.DataFrame([d for d in data if d["type"] == "C"], columns=["strike", "mid"])
    df_puts = pd.DataFrame([d for d in data if d["type"] == "P"], columns=["strike", "mid"])

    # Merge on strike
    df = pd.merge(df_calls, df_puts, on="strike", how="outer", suffixes=("_call", "_put"))
    df.sort_values("strike", inplace=True)

    # Display table
    st.dataframe(df.rename(columns={
        "mid_call": "Call (Mid)",
        "strike": "Strike",
        "mid_put": "Put (Mid)"
    }).reset_index(drop=True))
