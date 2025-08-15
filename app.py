import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "https://api.delta.exchange"

# ---------------- Fetch all BTC options ----------------
def get_btc_options():
    url = f"{BASE_URL}/v2/products"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json().get("result", [])
    
    options = [
        p for p in data
        if (p["symbol"].startswith("C-BTC") or p["symbol"].startswith("P-BTC"))
    ]
    return options

# ---------------- Find nearest expiry ----------------
def get_nearest_expiry(options):
    today = datetime.utcnow()
    future_options = [p for p in options if datetime.fromisoformat(p["settlement_time"].replace("Z", "+00:00")) > today]
    if not future_options:
        return None, []
    
    nearest = min(
        future_options,
        key=lambda x: datetime.fromisoformat(x["settlement_time"].replace("Z", "+00:00"))
    )
    nearest_expiry = nearest["settlement_time"]
    
    nearest_options = [
        p for p in future_options if p["settlement_time"] == nearest_expiry
    ]
    return nearest_expiry, nearest_options

# ---------------- Fetch mid price safely ----------------
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

# ---------------- Build options chain table ----------------
def build_options_chain(options):
    calls = [o for o in options if o["symbol"].startswith("C-BTC")]
    puts = [o for o in options if o["symbol"].startswith("P-BTC")]
    
    # Strike price is in o["strike_price"]
    strikes = sorted({o["strike_price"] for o in options})
    
    rows = []
    for strike in strikes:
        call_price = None
        put_price = None
        
        call = next((c for c in calls if c["strike_price"] == strike), None)
        if call:
            call_price = fetch_orderbook(call["symbol"])
        
        put = next((p for p in puts if p["strike_price"] == strike), None)
        if put:
            put_price = fetch_orderbook(put["symbol"])
        
        rows.append({
            "Call (Mid)": call_price,
            "Strike": strike,
            "Put (Mid)": put_price
        })
    
    return pd.DataFrame(rows)

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="BTC Options Chain", layout="wide")
st.title("₿ BTC Options Chain Viewer")

with st.spinner("Fetching BTC options..."):
    try:
        all_options = get_btc_options()
        expiry_datetime, nearest_options = get_nearest_expiry(all_options)
        
        if not nearest_options:
            st.error("Could not fetch nearest expiry.")
        else:
            expiry_ist = datetime.fromisoformat(expiry_datetime.replace("Z", "+00:00")) + timedelta(hours=5, minutes=30)
            st.subheader(f"Nearest Expiry: {expiry_ist.strftime('%d-%b-%Y %I:%M %p IST')}")
            
            df = build_options_chain(nearest_options)
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")
