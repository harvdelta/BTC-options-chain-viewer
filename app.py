import streamlit as st
import requests
import pandas as pd
import time, hmac, hashlib
from datetime import datetime
from urllib.parse import urlencode

BASE_URL = "https://api.delta.exchange"

# Load API keys from secrets
API_KEY = st.secrets["DELTA_API_KEY"]
API_SECRET = st.secrets["DELTA_API_SECRET"]

def sign_request(method, path, params=None):
    """Generate signed headers for Delta Exchange private API."""
    ts = str(int(time.time()))
    query = urlencode(params) if params else ""
    sig_payload = f"{method.upper()}{ts}/{path}"
    if query:
        sig_payload += f"?{query}"
    signature = hmac.new(API_SECRET.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()

    headers = {
        "api-key": API_KEY,
        "timestamp": ts,
        "signature": signature
    }
    return headers

def get_all_contracts():
    """Fetch all option contracts (authenticated request)."""
    path = "v2/products"
    url = f"{BASE_URL}/{path}"
    headers = sign_request("GET", path)
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()["result"]
    return [c for c in data if c["contract_type"] in ["call_option", "put_option"]]

def get_nearest_expiry_contracts():
    contracts = get_all_contracts()
    btc_contracts = [c for c in contracts if c["underlying_asset"]["symbol"] == "BTC"]
    expiries = sorted(set(c["settlement_time"] for c in btc_contracts))
    nearest_expiry = expiries[0]
    nearest_contracts = [c for c in btc_contracts if c["settlement_time"] == nearest_expiry]
    return nearest_contracts, nearest_expiry

def fetch_orderbook(product_id):
    path = f"v2/l2orderbook/{product_id}"
    url = f"{BASE_URL}/{path}"
    headers = sign_request("GET", path)
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()["result"]
    bid = float(data["buy_book"][0]["price"]) if data["buy_book"] else None
    ask = float(data["sell_book"][0]["price"]) if data["sell_book"] else None
    return bid, ask

def build_option_chain():
    contracts, expiry = get_nearest_expiry_contracts()
    strikes = sorted(set(c["strike_price"] for c in contracts))

    rows = []
    for strike in strikes:
        call = next((c for c in contracts if c["strike_price"] == strike and c["contract_type"] == "call_option"), None)
        put = next((c for c in contracts if c["strike_price"] == strike and c["contract_type"] == "put_option"), None)

        call_bid, call_ask = fetch_orderbook(call["id"]) if call else (None, None)
        put_bid, put_ask = fetch_orderbook(put["id"]) if put else (None, None)

        rows.append({
            "Call Bid": call_bid,
            "Call Ask": call_ask,
            "Call Mark": call["mark_price"] if call else None,
            "Call OI": call["open_interest"] if call else None,
            "Call Delta": call["greeks"]["delta"] if call else None,
            "Call IV": call["greeks"]["iv"] if call else None,
            "Strike": strike,
            "Put Bid": put_bid,
            "Put Ask": put_ask,
            "Put Mark": put["mark_price"] if put else None,
            "Put OI": put["open_interest"] if put else None,
            "Put Delta": put["greeks"]["delta"] if put else None,
            "Put IV": put["greeks"]["iv"] if put else None,
        })

    df = pd.DataFrame(rows)
    return df, expiry

# ---- Streamlit UI ----
st.set_page_config(page_title="BTC Option Chain", layout="wide")
st.title("BTC Options Chain - Nearest Expiry")

df, expiry = build_option_chain()
st.subheader(f"Nearest Expiry: {expiry} (UTC)")

st.dataframe(df.style.format(precision=2))
