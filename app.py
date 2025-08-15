import streamlit as st
import requests
import json

st.write("🔍 Testing bid/ask fetch for one symbol...")

symbol = "P-BTC-116400-160825"  # test one strike
url = f"https://api.delta.exchange/v2/tickers/{symbol}"

try:
    r = requests.get(url, timeout=5)
    st.write("Status Code:", r.status_code)

    data = r.json()
    st.write("Raw JSON:", json.dumps(data, indent=2))

    if "result" in data:
        bid = data["result"].get("best_bid_price")
        ask = data["result"].get("best_ask_price")
        st.write(f"✅ Best Bid: {bid}")
        st.write(f"✅ Best Ask: {ask}")
    else:
        st.error("❌ 'result' not found in API response")

except Exception as e:
    st.error(f"⚠️ Error: {e}")
