import streamlit as st
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd

BASE_URL = "https://api.delta.exchange"

def fetch_products():
    url = f"{BASE_URL}/v2/products"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["result"]

def get_nearest_expiry(products):
    btc_options = [p for p in products if p["symbol"].startswith(("C-BTC", "P-BTC"))]
    if not btc_options:
        return None, None

    # Find nearest expiry datetime
    for p in btc_options:
        p["expiry_dt"] = datetime.fromisoformat(p["settlement_time"].replace("Z", "+00:00"))

    nearest = min(btc_options, key=lambda x: x["expiry_dt"])
    expiry_date = nearest["expiry_dt"]

    # All products with same expiry
    same_expiry = [p for p in btc_options if p["expiry_dt"] == expiry_date]

    return expiry_date, same_expiry

def fetch_orderbook(symbol):
    url = f"{BASE_URL}/v2/l2orderbook/{symbol}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()["result"]

    best_bid = data["buy_book"][0]["price"] if data["buy_book"] else None
    best_ask = data["sell_book"][0]["price"] if data["sell_book"] else None

    if best_bid is not None and best_ask is not None:
        return round((best_bid + best_ask) / 2, 1)
    return None

def build_options_chain(products):
    chain = {}
    for p in products:
        strike = p["strike_price"]
        mid_price = fetch_orderbook(p["symbol"])
        if p["symbol"].startswith("C-BTC"):
            chain.setdefault(strike, {})["call"] = mid_price
        elif p["symbol"].startswith("P-BTC"):
            chain.setdefault(strike, {})["put"] = mid_price
    return chain

# Streamlit UI
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("📊 BTC Options Chain Viewer")

with st.spinner("Fetching BTC options data..."):
    try:
        products = fetch_products()
        expiry_date, nearest_products = get_nearest_expiry(products)
        if not nearest_products:
            st.error("No BTC options data found.")
        else:
            ist_expiry = expiry_date.astimezone(timezone(timedelta(hours=5, minutes=30)))
            st.markdown(f"**Nearest Expiry Date:** {ist_expiry.strftime('%d %b %Y, %I:%M %p IST')}")

            chain = build_options_chain(nearest_products)

            # Convert to DataFrame
            df = pd.DataFrame.from_dict(chain, orient="index").reset_index()
            df.columns = ["Strike", "Call (Mid)", "Put (Mid)"]
            df = df.sort_values(by="Strike").reset_index(drop=True)

            # Apply green/red style
            def color_val(val):
                if pd.isna(val):
                    return ""
                return f"color: {'green' if val >= 0 else 'red'}"

            st.dataframe(df.style.format({"Call (Mid)": "{:.1f}", "Put (Mid)": "{:.1f}"}))
    except Exception as e:
        st.error(f"Error: {e}")
