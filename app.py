import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

BASE_URL = "https://api.delta.exchange"

def fetch_products():
    url = f"{BASE_URL}/v2/products"
    resp = requests.get(url)
    data = resp.json()
    return data.get("result", [])

def filter_btc_options(products):
    return [p for p in products if p.get("symbol", "").startswith(("C-BTC", "P-BTC"))]

def get_nearest_expiry(options):
    now_utc = datetime.now(timezone.utc)
    future_options = []
    for p in options:
        settlement_str = p.get("settlement_time")
        if settlement_str:
            expiry_dt = datetime.fromisoformat(settlement_str.replace("Z", "+00:00"))
            if expiry_dt > now_utc:
                future_options.append(p)

    if not future_options:
        return None, []

    nearest_expiry = min(
        future_options,
        key=lambda x: datetime.fromisoformat(x["settlement_time"].replace("Z", "+00:00"))
    )["settlement_time"]

    nearest_options = [p for p in future_options if p.get("settlement_time") == nearest_expiry]
    return nearest_expiry, nearest_options

def fetch_orderbook(symbol):
    url = f"{BASE_URL}/v2/l2orderbook/{symbol}"
    resp = requests.get(url)
    data = resp.json()
    buy_book = data.get("buy_book", [])
    sell_book = data.get("sell_book", [])
    best_bid = float(buy_book[0]["price"]) if buy_book else None
    best_ask = float(sell_book[0]["price"]) if sell_book else None
    return best_bid, best_ask

# --- Streamlit UI ---
st.set_page_config(page_title="BTC Options Chain", layout="wide")
st.title("₿ BTC Options Chain Viewer")

with st.spinner("Fetching BTC options data..."):
    products = fetch_products()
    btc_options = filter_btc_options(products)
    expiry_str, nearest_opts = get_nearest_expiry(btc_options)

if not expiry_str:
    st.error("Could not fetch nearest expiry.")
else:
    expiry_dt_utc = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
    expiry_dt_ist = expiry_dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    st.subheader(f"Nearest Expiry: {expiry_dt_ist.strftime('%d-%m-%Y %I:%M %p IST')}")

    calls_data = []
    puts_data = []

    for opt in nearest_opts:
        symbol = opt.get("symbol", "")
        strike = opt.get("strike_price", None)
        opt_type = "C" if symbol.startswith("C-BTC") else "P"
        best_bid, best_ask = fetch_orderbook(symbol)
        mid_price = None
        if best_bid is not None and best_ask is not None:
            mid_price = (best_bid + best_ask) / 2
        row = {"strike": strike, "mid_price": mid_price}
        if opt_type == "C":
            calls_data.append(row)
        else:
            puts_data.append(row)

    calls_df = pd.DataFrame(calls_data).set_index("strike")
    puts_df = pd.DataFrame(puts_data).set_index("strike")

    # Merge for side-by-side display
    chain_df = calls_df.join(puts_df, lsuffix="_call", rsuffix="_put")
    chain_df = chain_df.sort_index()

    st.dataframe(chain_df, use_container_width=True)
