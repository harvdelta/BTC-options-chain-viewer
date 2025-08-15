import streamlit as st
import aiohttp
import asyncio
from datetime import datetime
import pytz

DELTA_BASE_URL = "https://api.delta.exchange"

# ------------------------
# Fetch nearest expiry
# ------------------------
async def get_nearest_expiry():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DELTA_BASE_URL}/v2/products") as resp:
            data = await resp.json()

    options = [p for p in data["result"] if p["product_type"] == "options" and p["underlying_asset"]["symbol"] == "BTC"]
    expiries = sorted(list(set([p["settlement_time"] for p in options])))

    if not expiries:
        return None, None

    nearest_expiry = expiries[0]
    expiry_datetime = datetime.fromisoformat(nearest_expiry.replace("Z", "+00:00")).astimezone(pytz.timezone("Asia/Kolkata"))

    nearest_expiry_products = [p for p in options if p["settlement_time"] == nearest_expiry]

    return expiry_datetime, nearest_expiry_products

# ------------------------
# Fetch mid price for a given symbol
# ------------------------
async def fetch_mid_price(session, symbol):
    try:
        async with session.get(f"{DELTA_BASE_URL}/v2/l2orderbook/{symbol}") as resp:
            data = await resp.json()
            bids = data["result"]["buy_levels"]
            asks = data["result"]["sell_levels"]

            if not bids or not asks:
                return symbol, None

            best_bid = float(bids[0]["price"])
            best_ask = float(asks[0]["price"])
            mid_price = round((best_bid + best_ask) / 2, 2)

            return symbol, mid_price
    except Exception:
        return symbol, None

# ------------------------
# Main async data fetcher
# ------------------------
async def fetch_all_mid_prices(products):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_mid_price(session, p["symbol"]) for p in products]
        results = await asyncio.gather(*tasks)
        return dict(results)

# ------------------------
# Build table for Streamlit
# ------------------------
def build_options_chain(products, prices):
    calls = {}
    puts = {}

    for p in products:
        strike = p["strike_price"]
        symbol = p["symbol"]
        mid_price = prices.get(symbol, None)

        if p["option_type"] == "call":
            calls[strike] = mid_price
        elif p["option_type"] == "put":
            puts[strike] = mid_price

    strikes = sorted(set(calls.keys()) | set(puts.keys()))
    table = []

    for strike in strikes:
        table.append({
            "Call Mid": calls.get(strike, None),
            "Strike": strike,
            "Put Mid": puts.get(strike, None)
        })

    return table

# ------------------------
# Streamlit App
# ------------------------
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")

st.title("📊 BTC Options Chain Viewer")

expiry_datetime, products = asyncio.run(get_nearest_expiry())

if not products:
    st.error("No options data found.")
else:
    st.subheader(f"Nearest Expiry Date: {expiry_datetime.strftime('%d %b %Y, %I:%M %p IST')}")

    prices = asyncio.run(fetch_all_mid_prices(products))
    table = build_options_chain(products, prices)

    st.table(table)
