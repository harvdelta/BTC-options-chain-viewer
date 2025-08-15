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
        return None, None

    btc_options = [
        p for p in data["result"]
        if p.get("contract_type") in ["call_options", "put_options"]
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
        and p.get("settlement_time")
    ]

    if not btc_options:
        return None, None

    btc_options.sort(key=lambda x: x["settlement_time"])
    nearest = btc_options[0]

    expiry_code = "-".join(nearest["symbol"].split("-")[:2])  # e.g. BTC-16AUG25
    expiry_date = nearest["settlement_time"]
    return expiry_date, expiry_code

# ---------- Fetch Options Chain ----------
def fetch_options_chain(expiry_code):
    url = f"{BASE_URL}/v2/tickers"
    data = requests.get(url).json()
    if not data.get("success") or "result" not in data:
        return []

    return [p for p in data["result"] if expiry_code in p["symbol"]]

# ---------- Convert UTC to IST ----------
def utc_to_ist(utc_str):
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
    utc_dt = utc_dt.replace(tzinfo=pytz.utc)
    ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata"))
    return ist_dt.strftime("%d %b %Y, %I:%M %p IST")

# ---------- Streamlit App ----------
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("📊 BTC Options Chain Viewer")

expiry_date, expiry_code = get_nearest_expiry()

if not expiry_code:
    st.error("Could not fetch nearest expiry.")
else:
    st.markdown(f"**Nearest Expiry Date:** {utc_to_ist(expiry_date)}")
    chain = fetch_options_chain(expiry_code)

    if not chain:
        st.warning("No options data found for this expiry.")
    else:
        # Split into calls & puts using symbol suffix
        calls = [c for c in chain if c["symbol"].endswith("-C")]
        puts = [p for p in chain if p["symbol"].endswith("-P")]

        # Sort by strike price
        calls.sort(key=lambda x: x["strike_price"])
        puts.sort(key=lambda x: x["strike_price"])

        strikes = sorted(set([c["strike_price"] for c in calls] + [p["strike_price"] for p in puts]))

        # Build table with Mark Prices only
        table = []
        for strike in strikes:
            call_mark = next((c["mark_price"] for c in calls if c["strike_price"] == strike), None)
            put_mark = next((p["mark_price"] for p in puts if p["strike_price"] == strike), None)
            table.append({"Call Mark Price": call_mark, "Strike": strike, "Put Mark Price": put_mark})

        df = pd.DataFrame(table)
        st.dataframe(df, use_container_width=True)
