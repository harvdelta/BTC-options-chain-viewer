import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
import re

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"
IST = pytz.timezone("Asia/Kolkata")

# ======================
# DIAGNOSTIC FUNCTIONS
# ======================

@st.cache_data(ttl=30)
def fetch_products():
    """Fetch all products from Delta Exchange with caching."""
    try:
        response = requests.get(f"{BASE_URL}/products", timeout=10)
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching products: {e}")
        return []

@st.cache_data(ttl=10)
def fetch_all_tickers():
    """Fetch all tickers in one API call."""
    try:
        response = requests.get(f"{BASE_URL}/tickers", timeout=10)
        response.raise_for_status()
        data = response.json().get("result", [])
        return {ticker["symbol"]: ticker for ticker in data}
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching tickers: {e}")
        return {}

@st.cache_data(ttl=30)
def fetch_single_ticker(symbol):
    """Fetch single ticker for comparison."""
    try:
        response = requests.get(f"{BASE_URL}/tickers/{symbol}", timeout=10)
        response.raise_for_status()
        return response.json().get("result", {})
    except requests.exceptions.RequestException as e:
        return None

def test_different_conversions(raw_value, expected_value):
    """Test different conversion factors to find the right one."""
    conversions = []
    
    # Test various divisors
    for divisor in [1, 10, 100, 1000, 10000, 100000, 1000000]:
        converted = raw_value / divisor
        difference = abs(converted - expected_value)
        conversions.append({
            "Divisor": divisor,
            "Raw Value": raw_value,
            "Converted": f"{converted:.6f}",
            "Expected": expected_value,
            "Difference": f"{difference:.6f}",
            "Match": "✅" if difference < 0.1 else "❌"
        })
    
    # Test multipliers
    for multiplier in [0.1, 0.01, 0.001, 0.0001, 0.00001]:
        converted = raw_value * multiplier
        difference = abs(converted - expected_value)
        conversions.append({
            "Divisor": f"×{multiplier}",
            "Raw Value": raw_value,
            "Converted": f"{converted:.6f}",
            "Expected": expected_value,
            "Difference": f"{difference:.6f}",
            "Match": "✅" if difference < 0.1 else "❌"
        })
    
    return pd.DataFrame(conversions)

# ======================
# STREAMLIT UI
# ======================
st.set_page_config(page_title="🔍 Options Price Diagnostic Tool", layout="wide")
st.title("🔍 BTC Options Price Diagnostic Tool")

st.markdown("""
**Goal**: Find the exact conversion factor to match real market prices.
You mentioned: **Strike $128,400 should show ~$0.50**, but code shows **$8.05**
""")

# Fetch data
with st.spinner("Fetching data..."):
    products = fetch_products()
    all_tickers = fetch_all_tickers()

if not products or not all_tickers:
    st.error("Failed to fetch data")
    st.stop()

# Filter BTC options
btc_options = [p for p in products if p.get("symbol", "").startswith(("C-BTC", "P-BTC"))]

if not btc_options:
    st.error("No BTC options found")
    st.stop()

st.success(f"Found {len(btc_options)} BTC options")

# Let user select a specific option to analyze
st.subheader("🎯 Select an Option to Analyze")

# Create a dropdown with option details
option_choices = {}
for opt in btc_options[:20]:  # Show first 20 options
    symbol = opt["symbol"]
    strike = opt.get("strike_price", "N/A")
    option_choices[f"{symbol} (Strike: {strike})"] = opt

selected_option_key = st.selectbox("Choose an option:", list(option_choices.keys()))
selected_option = option_choices[selected_option_key]

if selected_option:
    symbol = selected_option["symbol"]
    raw_strike = float(selected_option.get("strike_price", 0))
    
    st.subheader(f"🔬 Analyzing: {symbol}")
    
    # Display raw product data
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**📊 Raw Product Data:**")
        st.json({
            "symbol": selected_option.get("symbol"),
            "strike_price": selected_option.get("strike_price"),
            "tick_size": selected_option.get("tick_size"),
            "contract_value": selected_option.get("contract_value"),
            "contract_unit_currency": selected_option.get("contract_unit_currency"),
        })
    
    with col2:
        # Get ticker data
        ticker_data = all_tickers.get(symbol)
        single_ticker = fetch_single_ticker(symbol)
        
        st.write("**📈 Raw Ticker Data:**")
        if ticker_data:
            quotes = ticker_data.get("quotes", {})
            st.json({
                "symbol": ticker_data.get("symbol"),
                "best_bid": quotes.get("best_bid"),
                "best_ask": quotes.get("best_ask"),
                "mark_price": ticker_data.get("mark_price"),
                "underlying_asset": ticker_data.get("underlying_asset")
            })
        else:
            st.error("No ticker data found")

    # Manual input for expected values
    st.subheader("📝 Manual Input (Your Expected Values)")
    
    col1, col2 = st.columns(2)
    with col1:
        expected_strike = st.number_input(
            "Expected Strike Price ($)", 
            value=128400.0,
            help="What should the strike price show? (e.g., 128400)"
        )
    
    with col2:
        expected_option_price = st.number_input(
            "Expected Option Price ($)", 
            value=0.50,
            help="What should this option cost? (e.g., 0.50)"
        )
    
    if ticker_data:
        quotes = ticker_data.get("quotes", {})
        raw_bid = float(quotes.get("best_bid", 0)) if quotes.get("best_bid") else 0
        raw_ask = float(quotes.get("best_ask", 0)) if quotes.get("best_ask") else 0
        raw_mid = (raw_bid + raw_ask) / 2 if raw_bid and raw_ask else 0
        raw_mark = float(ticker_data.get("mark_price", 0)) if ticker_data.get("mark_price") else 0
        
        # Test conversions for strike price
        st.subheader("🧮 Strike Price Conversion Analysis")
        if raw_strike > 0:
            strike_df = test_different_conversions(raw_strike, expected_strike)
            st.dataframe(strike_df, use_container_width=True)
        
        # Test conversions for option price
        st.subheader("💰 Option Price Conversion Analysis")
        
        # Test mid price
        if raw_mid > 0:
            st.write(f"**Testing Mid Price**: Raw={(raw_bid + raw_ask)/2:.2f}")
            mid_df = test_different_conversions(raw_mid, expected_option_price)
            st.dataframe(mid_df, use_container_width=True)
        
        # Test mark price
        if raw_mark > 0:
            st.write(f"**Testing Mark Price**: Raw={raw_mark:.2f}")
            mark_df = test_different_conversions(raw_mark, expected_option_price)
            st.dataframe(mark_df, use_container_width=True)
        
        # Summary of findings
        st.subheader("🎯 Conversion Factor Findings")
        
        # Find best matches
        if raw_strike > 0:
            best_strike_factor = raw_strike / expected_strike
            st.write(f"**Strike Price**: Divide by `{best_strike_factor:.0f}` ({raw_strike} ÷ {best_strike_factor:.0f} = {raw_strike/best_strike_factor:.0f})")
        
        if raw_mid > 0:
            best_mid_factor = raw_mid / expected_option_price
            st.write(f"**Mid Price**: Divide by `{best_mid_factor:.0f}` ({raw_mid:.2f} ÷ {best_mid_factor:.0f} = {raw_mid/best_mid_factor:.4f})")
        
        if raw_mark > 0:
            best_mark_factor = raw_mark / expected_option_price
            st.write(f"**Mark Price**: Divide by `{best_mark_factor:.0f}` ({raw_mark:.2f} ÷ {best_mark_factor:.0f} = {raw_mark/best_mark_factor:.4f})")
        
        # Generate corrected code
        if st.button("🚀 Generate Corrected Code"):
            strike_factor = int(raw_strike / expected_strike) if raw_strike > 0 else 1
            price_factor = int(raw_mid / expected_option_price) if raw_mid > 0 else 1
            
            st.code(f"""
# Corrected conversion factors based on analysis:
def parse_option_details(products):
    # ... existing code ...
    strike = float(product.get("strike_price", 0)) / {strike_factor}  # Divide by {strike_factor}
    # ... rest of code ...

def get_mid_price(ticker_data):
    # ... existing code ...
    return mid / {price_factor}  # Divide by {price_factor}
""", language="python")

    # Additional API endpoints to test
    st.subheader("🔍 Alternative API Endpoints")
    
    st.write("**Test other Delta Exchange endpoints:**")
    
    test_endpoints = [
        f"{BASE_URL}/products/{selected_option.get('id')}",
        f"{BASE_URL}/l2orderbook/{symbol}",
        f"https://publicapi.deltaexchange.io/v1/tickers",
    ]
    
    for endpoint in test_endpoints:
        if st.button(f"Test: {endpoint}"):
            try:
                response = requests.get(endpoint, timeout=10)
                if response.status_code == 200:
                    st.json(response.json())
                else:
                    st.error(f"HTTP {response.status_code}: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
