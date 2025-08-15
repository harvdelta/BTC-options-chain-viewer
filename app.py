import streamlit as st
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "https://api.delta.exchange"

# -------- Get Nearest Expiry Code --------
def get_nearest_expiry_code():
    url = f"{BASE_URL}/v2/tickers"
    r = requests.get(url).json()

    if not r.get("success") or "result" not in r:
        return None, []

    # Filter BTC options only
    options = [t for t in r["result"] if t["symbol"].startswith(("C-BTC", "P-BTC"))]

    if not options:
        return None, []

    # Extract expiry code (last part of symbol, DDMMYY)
    for t in options:
        t["expiry_code"] = t["symbol"].split("-")[-1]

    # Pick the earliest expiry
    unique_expiries = sorted(set(t["expiry_code"] for t in options))
    nearest_expiry = unique_expiries[0]

    return nearest_expiry, options

# -------- Get Options Chain for Expiry --------
def get_options_chain(expiry_code, all_options):
    # Filter only nearest expiry
    nearest = [t for t in all_options if t["expiry_code"] == expiry_code]

    # Separate Calls and Puts
    calls = [t for t in nearest if t["symbol"].startswith("C-BTC")]
    puts = [t for t in nearest if t["symbol"].startswith("P-BTC")]

    # Extract strike price (3rd part of symbol)
    for c in calls:
        c["strike"] = int(c["symbol"].split("-")[2])
    for p in puts:
        p["strike"] = int(p["symbol"].split("-")[2])

    # Sort by strike
    calls.sort(key=lambda x: x["strike"])
    puts.sort(key=lambda x: x["strike"])

    # Build table
    strikes = sorted(set([c["strike"] for c in calls] + [p["strike"] for p in puts]))

    table = []
    for strike in strikes:
        call_mark = next((c["mark_price"] for c in calls if c["strike"] == strike), None)
        put_mark = next((p["mark_price"] for p in puts if p["strike"] == strike), None)
        table.append({
            "Call Mark Price": call_mark,
            "Strike": strike,
            "Put Mark Price": put_mark
        })

    return pd.DataFrame(table)

# -------- Convert Expiry Code to Date --------
def expiry_code_to_date(code):
    try:
        dt = datetime.strptime(code, "%d%m%y")
        return dt.strftime("%d %b %Y")
    except:
        return code

# -------- Streamlit UI --------
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("📊 BTC Options Chain Viewer")

expiry_code, all_options = get_nearest_expiry_code()

if not expiry_code:
    st.error("Could not fetch options data.")
else:
    expiry_date_str = expiry_code_to_date(expiry_code)
    st.markdown(f"**Nearest Expiry Date:** {expiry_date_str}")

    df = get_options_chain(expiry_code, all_options)
    if df.empty:
        st.warning("No options data found for this expiry.")
    else:
        st.dataframe(df, use_container_width=True)
