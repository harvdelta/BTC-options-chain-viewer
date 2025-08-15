import streamlit as st
import aiohttp
import asyncio
import pytz
from datetime import datetime

DELTA_BASE_URL = "https://api.delta.exchange"

# ---------------------------
# Fetch nearest BTC options expiry
# ---------------------------
async def get_nearest_expiry():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DELTA_BASE_URL}/v2/products") as resp:
            data = await resp.json()

    if "result" not in data or not isinstance(data["result"], list):
        return None, None

    options = [
        p for p in data["result"]
        if p.get("product_type") == "options"
        and p.get("underlying_asset", {}).get("symbol") == "BTC"
    ]

    if not options:
        return None, None

    expiries = sorted(list(set([
        p.get("settlement_time")
        for p in options if p.get("settlement_time")
    ])))
    if not expiries:
        return None, None

    nearest_expiry = expiries[0]
    expiry_datetime = datetime.fromisoformat(
        nearest_expiry.replace("Z", "+00:00")
    ).astimezone(pytz.timezone("Asia/Kolkata"))

    nearest_expiry_products = [
        p for p in options if p.get("settlement_time") == nearest_expiry
    ]

    return expiry_datetime, nearest_expiry_products

# ---------------------------
# Fetch mid-price for a product
# ---------------------------
async def fetch_mid_price(session, symbol):
    url = f"{DELTA_BASE_URL}/v2/l2orderbook/{symbol}"
    try:
        async with session.get(url) as resp:
            data = await resp.json()

        if "result" not in data:
            return None

        buy_levels = data["result"].get("buy_levels", [])
        sell_levels = data["result"].get("sell_levels", [])

        if not buy_levels or not sell_levels:
            return None

        best_bid = buy_levels[0].get("price")
        best_ask = sell_levels[0].get("price")

        if best_bid is None or best_ask is None:
            return None

        return (best_bid + best_ask) / 2
    except Exception:
        return None

# ---------------------------
# Main table builder
# ---------------------------
async def build_options_table(products):
    calls = {}
    puts = {}

    async with aiohttp.ClientSession() as session:
        tasks = []
        for p in products:
            tasks.append(fetch_mid_price(session, p["symbol"]))

        mid_prices = await asyncio.gather(*tasks)

    for idx, p in enumerate(products):
        strike = p.get("strike_price")
        option_type = p.get("option_type")
        price = mid_prices[idx]

        if strike is None or option_type not in ["call", "put"]:
            continue

        if option_type == "call":
            calls[strike] = price
        else:
            puts[strike] = price

    strikes = sorted(set(calls.keys()) | set(puts.keys()))

    table = []
    for strike in strikes:
        table.append({
            "Call Mid": calls.get(strike),
            "Strike": strike,
            "Put Mid": puts.get(strike)
        })

    return table

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="₿ BTC Options Chain Viewer", layout="wide")
st.title("₿ BTC Options Chain Viewer")

expiry_datetime, products = asyncio.run(get_nearest_expiry())

if not products:
    st.error("Could not fetch nearest expiry.")
else:
    st.write(f"**Nearest Expiry:** {expiry_datetime.strftime('%d-%m-%Y %H:%M %p')} IST")

    table = asyncio.run(build_options_table(products))
    st.table(table)
