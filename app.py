import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

BASE_URL = "https://api.delta.exchange"

def get_nearest_expiry():
    url = f"{BASE_URL}/v2/products"
    data = requests.get(url).json()

    if not data.get("success") or "result" not in data:
        return None

    # Filter only BTC options
    btc_options = [
        p for p in data["result"]
        if p.get("contract_type") in ["call_options", "put_options"]
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
        and p.get("settlement_time")
    ]

    if not btc_options:
        return None

    # Sort by settlement time
    btc_options.sort(key=lambda x: x["settlement_time"])
    return btc_options[0]["settlement_time"]

def fetch_options_chain(expiry):
    url = f"{BASE_URL}/v2/tickers"
    data = requests.get(url).json()
    if not data.get("success") or "result" not in data:
        return []
    chain = [p for p in data["result"] if expiry in p["symbol"]]
    return chain

def utc_to_ist(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        ist_dt = utc_dt + timedelta(hours=5, minutes=30)
        return ist_dt.strftime('%d %b %Y, %I:%M %p IST')
    except Exception:
        return utc_time_str

st.set_page_config(page_title="BTC Options Chain Viewer", page_icon="📊", layout="wide")
st.title("📊 BTC Options Chain Viewer")

expiry = get_nearest_expiry()
if not expiry:
    st.error("Could not fetch nearest expiry.")
    st.stop()

expiry_display = utc_to_ist(expiry)
st.write(f"**Nearest Expiry Date:** {expiry_display}")

chain = fetch_options_chain(expiry)
if not chain:
    st.warning("No options data found for this expiry.")
    st.stop()

df = pd.DataFrame(chain)
df["strike"] = df["symbol"].str.extract(r"(\d+)").astype(float)
df["type"] = df["symbol"].str.extract(r"-(C|P)$")
df["mark_display"] = df["mark_price"]

calls = df[df["type"] == "C"][["strike", "mark_display"]].rename(columns={"mark_display": "Calls (Mark)"})
puts = df[df["type"] == "P"][["strike", "mark_display"]].rename(columns={"mark_display": "Puts (Mark)"})

table = pd.merge(calls, puts, on="strike", how="outer").sort_values("strike")
table = table.set_index("strike")

st.dataframe(table)
