import streamlit as st
import aiohttp
import asyncio

DELTA_BASE_URL = "https://api.delta.exchange"

async def debug_fetch_products():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DELTA_BASE_URL}/v2/products") as resp:
            try:
                data = await resp.json()
            except:
                text_data = await resp.text()
                st.error("API did not return JSON, here’s the raw response:")
                st.code(text_data)
                return

    st.subheader("Raw API JSON:")
    st.json(data)

st.set_page_config(page_title="API Debug", layout="wide")
st.title("Debugging /v2/products response")

asyncio.run(debug_fetch_products())
