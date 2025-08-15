import streamlit as st
import requests
import pandas as pd

BASE_URL = "https://api.delta.exchange"

def get_nearest_expiry():
    url = f"{BASE_URL}/v2/products"
    data = requests.get(url).json()
    options = [p for p in data["result"] if p["product_type"] == "options"]
    expiries = sorted(set([p["settlement_time"] for p in options]))
    return expiries[0] if expiries else None

def fetch_options_chain(expiry):
    url = f"{BASE_URL}/v2/tickers"
    data = requests.get(url).json()
    chain = [p for p in data["result"] if expiry in p["symbol"]]
    return chain

st.set_page_config(page_title="BTC Options Chain", page_icon="📊", layout="wide")
st.title("📊 BTC Options Chain – Nearest Expiry (Mark Prices Only)")

expiry = get_nearest_expiry()
if not expiry:
    st.error("Could not fetch nearest expiry.")
    st.stop()

st.write(f"**Nearest Expiry:** {expiry}")

chain = fetch_options_chain(expiry)
if not chain:
    st.warning("No options data found for this expiry.")
    st.stop()

df = pd.DataFrame(chain)

# Extract strike and type (C/P)
df["strike"] = df["symbol"].str.extract(r"(\d+)").astype(float)
df["type"] = df["symbol"].str.extract(r"-(C|P)$")

# Keep only mark price
df["mark_display"] = df["mark_price"]

# Separate calls and puts
calls = df[df["type"] == "C"][["strike", "mark_display"]].rename(columns={"mark_display": "Calls (Mark)"})
puts = df[df["type"] == "P"][["strike", "mark_display"]].rename(columns={"mark_display": "Puts (Mark)"})

# Merge into single table
table = pd.merge(calls, puts, on="strike", how="outer").sort_values("strike")
table = table.set_index("strike")

st.dataframe(table)
