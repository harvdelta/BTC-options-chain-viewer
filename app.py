import streamlit as st
import requests
from datetime import datetime
import pytz
import pandas as pd

BASE_URL = "https://api.delta.exchange"

# ---------- Fetch Nearest Expiry ----------
def get_nearest_expiry():
    url = f"{BASE_URL}/v2/products"
    data = requests.get(url).json()

    if not data.get("success") or "result" not in data:
        return None, None, []

    btc_options = [
        p for p in data["result"]
        if p.get("contract_type") in ["call_options", "put_options"]
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
        and p.get("settlement_time")
    ]

    if not btc_options:
        return None, None, []

    # Sort by expiry
    btc_options.sort(key=lambda x: x["settlement_time"])
    nearest_expiry_time = btc_options[0]["settlement_time"]

    # Filter all products for the same expiry
    nearest_expiry_products = [
        p for p in btc_options if p["settlement_time"] == nearest_expiry_time
    ]

    product_ids = [p["id"] for p in nearest_expiry_products]

    return nearest_expiry_time, product_ids, nearest_expiry_products

# ---------- Fetch Options Chain ----------
def fetch_options_chain(product_ids):
    url = f"{BASE_URL}/v2/tickers"
    data = requests.get(url).json()
    if not data.get("success") or "result" not in data:
        return []

    return [p for p in data["result"] if p["product_id"] in product_ids]

# ---------- Convert UTC to IST ----------
def utc_to_ist(utc_str):
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
    utc_dt = utc_dt.replace(tzinfo=pytz.utc)
    ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
    return ist_dt.strftime("%d %b %Y, %I:%M %p IST")

# ---------- Streamlit App ----------
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("📊 BTC Options Chain Viewer")

expiry_date, product_ids, products = get_nearest_expiry()

if not product_ids:
    st.error("Could not fetch nearest expiry.")
else:
    st.markdown(f"**Nearest Expiry Date:** {utc_to_ist(expiry_date)}")
    chain = fetch_options_chain(product_ids)

    if not chain:
        st.warning("No options data found for this expiry.")
    else:
        # Map strike prices from product data
        strike_map = {p["id"]: p["strike_price"] for p in products}

        # Split calls and puts
        calls = [c for c in chain if c["symbol"].endswith("-C")]
        puts = [p for p in chain if p["symbol"].endswith("-P")]

        # Add strike price to each record
        for c in calls:
            c["strike_price"] = strike_map.get(c["product_id"])
        for p in puts:
            p["strike_price"] = strike_map.get(p["product_id"])

        # Sort by strike price
        calls.sort(key=lambda x: x["strike_price"])
        puts.sort(key=lambda x: x["strike_price"])

        strikes = sorted(set([c["strike_price"] for c in calls] + [p["strike_price"] for p in puts]))

        table = []
        for strike in strikes:
            call_mark = next((c["mark_price"] for c in calls if c["strike_price"] == strike), None)
            put_mark = next((p["mark_price"] for p in puts if p["strike_price"] == strike), None)
            table.append({
                "Call Mark Price": call_mark,
                "Strike": strike,
                "Put Mark Price": put_mark
            })

        df = pd.DataFrame(table)
        st.dataframe(df, use_container_width=True)
