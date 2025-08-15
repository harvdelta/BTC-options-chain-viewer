import streamlit as st
import requests
from datetime import datetime
import pytz

BASE_URL = "https://api.india.delta.exchange/v2"

# Fetch nearest expiry date for BTC options
def get_nearest_expiry():
    url = f"{BASE_URL}/products"
    r = requests.get(url)
    r.raise_for_status()
    products = r.json().get("result", [])
    btc_options = [
        p for p in products
        if p.get("product_type") == "options"
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
    ]
    expiries = sorted(set([p["settlement_time"] for p in btc_options]))
    if not expiries:
        return None, []
    nearest_expiry = expiries[0]
    nearest_expiry_products = [
        p for p in btc_options if p["settlement_time"] == nearest_expiry
    ]
    return nearest_expiry, nearest_expiry_products

# Fetch mark price for a given symbol
def fetch_mark_price(symbol):
    url = f"{BASE_URL}/tickers/{symbol}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json().get("result", {})
    return round(float(data.get("mark_price", 0)), 2)

st.title("₿ BTC Options Chain Viewer")

expiry, products = get_nearest_expiry()

if expiry and products:
    try:
        expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        expiry_ist = expiry_dt.astimezone(pytz.timezone("Asia/Kolkata"))
        expiry_str = expiry_ist.strftime("%d-%m-%Y %I:%M %p IST")
    except Exception:
        expiry_str = expiry

    st.markdown(f"**Nearest Expiry:** {expiry_str}")
    now_ist = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y %I:%M:%S %p IST")
    st.markdown(f"**Data as of:** {now_ist}")

    strikes = sorted(set([p["strike_price"] for p in products]))
    table_data = []
    for strike in strikes:
        call_symbol = next((p["symbol"] for p in products if p["strike_price"] == strike and p["option_type"] == "call"), None)
        put_symbol = next((p["symbol"] for p in products if p["strike_price"] == strike and p["option_type"] == "put"), None)

        call_price = fetch_mark_price(call_symbol) if call_symbol else None
        put_price = fetch_mark_price(put_symbol) if put_symbol else None

        table_data.append({
            "Strike": strike,
            "Call Mark Price": call_price,
            "Put Mark Price": put_price
        })

    st.dataframe(table_data, use_container_width=True)
else:
    st.error("Could not fetch nearest expiry.")
