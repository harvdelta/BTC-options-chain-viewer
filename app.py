import streamlit as st
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "https://api.delta.exchange"

def get_nearest_expiry():
    url = f"{BASE_URL}/v2/products"
    data = requests.get(url).json()

    # DEBUG: Show first few entries from API
    st.write("🔍 API Raw Products Data (First 5 entries):")
    st.json(data.get("result", [])[:5])

    if not data.get("success") or "result" not in data:
        return None

    options = []
    for p in data["result"]:
        symbol = p.get("symbol", "")
        expiry_time = p.get("settlement_time")
        # Match BTC options by symbol pattern and settlement_time
        if "BTC" in symbol and expiry_time:
            options.append(expiry_time)

    if not options:
        return None

    expiries = sorted(set(options))
    return expiries[0] if expiries else None

def fetch_options_chain(expiry):
    url = f"{BASE_URL}/v2/tickers"
    data = requests.get(url).json()
    if not data.get("success") or "result" not in data:
        return []
    chain = [p for p in data["result"] if expiry in p["symbol"]]
    return chain

st.set_page_config(page_title="BTC Options Chain Debug", page_icon="📊", layout="wide")
st.title("📊 BTC Options Chain – DEBUG MODE")

expiry = get_nearest_expiry()
if not expiry:
    st.error("Could not fetch nearest expiry.")
    st.stop()

# Display expiry date in readable format
try:
    expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    expiry_display = expiry_dt.strftime('%d %b %Y, %I:%M %p UTC')
except ValueError:
    expiry_display = expiry

st.write(f"**Nearest Expiry Date:** {expiry_display}")

chain = fetch_options_chain(expiry)
if not chain:
    st.warning("No options data found for this expiry.")
    st.stop()

df = pd.DataFrame(chain)

# Extract strike and type
df["strike"] = df["symbol"].str.extract(r"(\d+)").astype(float)
df["type"] = df["symbol"].str.extract(r"-(C|P)$")
df["mark_display"] = df["mark_price"]

# Split into calls and puts
calls = df[df["type"] == "C"][["strike", "mark_display"]].rename(columns={"mark_display": "Calls (Mark)"})
puts = df[df["type"] == "P"][["strike", "mark_display"]].rename(columns={"mark_display": "Puts (Mark)"})

table = pd.merge(calls, puts, on="strike", how="outer").sort_values("strike")
table = table.set_index("strike")

st.dataframe(table)
