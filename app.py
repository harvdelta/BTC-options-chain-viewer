import streamlit as st
import aiohttp
import asyncio
from datetime import datetime
import pytz
import pandas as pd

DELTA_BASE_URL = "https://api.delta.exchange"

# ---------------------------
# API fetchers
# ---------------------------
async def get_all_products():
    """Fetch all products from Delta API in one call."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DELTA_BASE_URL}/v2/products?page_size=2000") as resp:
            data = await resp.json()

    if not data.get("success") or "result" not in data:
        return []

    return data["result"]

async def get_orderbook(product_id):
    """Fetch bid/ask for a product to calculate mid price."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DELTA_BASE_URL}/v2/l2orderbook/{product_id}") as resp:
            data = await resp.json()

    if not data.get("success") or "result" not in data:
        return None, None

    bids = data["result"].get("buy", [])
    asks = data["result"].get("sell", [])

    bid_price = float(bids[0]["price"]) if bids else None
    ask_price = float(asks[0]["price"]) if asks else None

    return bid_price, ask_price

# ---------------------------
# Expiry finder
# ---------------------------
async def get_nearest_expiry():
    products = await get_all_products()

    options = [
        p for p in products
        if p.get("product_type") == "options"
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
    ]

    if not options:
        return None, None

    expiries = sorted(list(set(p.get("settlement_time") for p in options if p.get("settlement_time"))))
    if not expiries:
        return None, None

    nearest_expiry = expiries[0]
    expiry_datetime = datetime.fromisoformat(nearest_expiry.replace("Z", "+00:00")).astimezone(pytz.timezone("Asia/Kolkata"))

    nearest_expiry_products = [p for p in options if p.get("settlement_time") == nearest_expiry]

    return expiry_datetime, nearest_expiry_products

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="₿ BTC Options Chain Viewer", layout="wide")
st.title("₿ BTC Options Chain Viewer")

with st.spinner("Fetching nearest expiry and option chain data..."):
    expiry_datetime, products = asyncio.run(get_nearest_expiry())

if expiry_datetime is None or not products:
    st.error("Could not fetch nearest expiry.")
else:
    st.success(f"Nearest Expiry: {expiry_datetime.strftime('%d-%m-%Y %I:%M %p IST')}")

    # Organise products by strike & type
    calls = [p for p in products if p.get("option_type") == "call"]
    puts = [p for p in products if p.get("option_type") == "put"]

    data_rows = []
    for call in calls:
        strike = call.get("strike_price")
        put = next((p for p in puts if p.get("strike_price") == strike), None)

        # Fetch mid prices
        call_bid, call_ask = asyncio.run(get_orderbook(call["id"]))
        put_bid, put_ask = asyncio.run(get_orderbook(put["id"])) if put else (None, None)

        call_mid = (call_bid + call_ask) / 2 if call_bid and call_ask else None
        put_mid = (put_bid + put_ask) / 2 if put_bid and put_ask else None

        data_rows.append({
            "Strike": strike,
            "Call Mid Price": call_mid,
            "Put Mid Price": put_mid
        })

    df = pd.DataFrame(data_rows)
    st.dataframe(df, use_container_width=True)
