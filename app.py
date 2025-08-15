import requests
import pandas as pd

# Delta Exchange API URL for products
BASE_URL = "https://api.delta.exchange/v2/products"

# Target strike price
TARGET_STRIKE = "128400"

# Fetch all products
resp = requests.get(BASE_URL)
data = resp.json()

if not data.get("success", False):
    raise Exception("Failed to fetch products")

results = data["result"]

# Filter for BTC options with the target strike
target_options = [
    p for p in results
    if p["underlying_asset_symbol"] == "BTC"
    and p.get("strike_price") == TARGET_STRIKE
    and "option_type" in p
]

if not target_options:
    raise Exception(f"No options found for strike {TARGET_STRIKE}")

rows = []

for opt in target_options:
    opt_type = "Call" if opt["option_type"] == "call" else "Put"
    quotes = opt.get("quotes", {})

    bid = float(quotes.get("best_bid", 0)) if quotes.get("best_bid") else None
    ask = float(quotes.get("best_ask", 0)) if quotes.get("best_ask") else None
    mark = float(opt.get("mark_price", 0)) if opt.get("mark_price") else None
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None

    rows.append({
        "Option Type": opt_type,
        "Bid": bid,
        "Ask": ask,
        "Mark": mark,
        "Mid": mid
    })

# Convert to DataFrame
df = pd.DataFrame(rows)

print(df)

# If using Streamlit, uncomment:
# import streamlit as st
# st.title(f"BTC Options Data for Strike {TARGET_STRIKE}")
# st.table(df)
