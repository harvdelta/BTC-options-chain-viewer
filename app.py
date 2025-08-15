import streamlit as st
import requests
import json

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"

st.set_page_config(page_title="🎯 128400 Strike Data", layout="wide")
st.title("🎯 Raw Data for 128400 Strike Only")

# Step 1: Find the exact symbol for 128400 strike
st.subheader("Step 1: Finding 128400 Strike Symbol...")

try:
    products_response = requests.get(f"{BASE_URL}/products", timeout=10)
    products_response.raise_for_status()
    products = products_response.json().get("result", [])
    
    # Find 128400 strike options
    target_symbols = []
    for product in products:
        symbol = product.get("symbol", "")
        if symbol.startswith(("C-BTC", "P-BTC")):
            strike_price = str(product.get("strike_price", ""))
            if "128400" in strike_price:
                target_symbols.append({
                    "symbol": symbol,
                    "strike_price": product.get("strike_price"),
                    "product_id": product.get("id"),
                    "product": product
                })
    
    if target_symbols:
        st.success(f"✅ Found {len(target_symbols)} options with 128400 strike:")
        for item in target_symbols:
            st.write(f"- **{item['symbol']}** (Strike: {item['strike_price']})")
    else:
        st.error("❌ No 128400 strike found. Let's see available strikes...")
        # Show some strikes for reference
        strikes = []
        for product in products:
            symbol = product.get("symbol", "")
            if symbol.startswith(("C-BTC", "P-BTC")):
                strikes.append(product.get("strike_price"))
        strikes = sorted(set(strikes))[:10]
        st.write(f"Available strikes (first 10): {strikes}")
        st.stop()

except requests.exceptions.RequestException as e:
    st.error(f"❌ Error: {e}")
    st.stop()

# Step 2: Get ticker data for 128400 strike options
st.subheader("Step 2: Raw Ticker Data for 128400 Strike")

for item in target_symbols:
    symbol = item["symbol"]
    st.write(f"\n**📊 Analyzing: {symbol}**")
    
    # Get ticker data
    try:
        ticker_response = requests.get(f"{BASE_URL}/tickers/{symbol}", timeout=10)
        ticker_response.raise_for_status()
        ticker_data = ticker_response.json().get("result", {})
        
        if ticker_data:
            # Extract key values
            quotes = ticker_data.get("quotes", {})
            
            raw_data = {
                "Symbol": symbol,
                "Best Bid": quotes.get("best_bid"),
                "Best Ask": quotes.get("best_ask"),
                "Mark Price": ticker_data.get("mark_price"),
                "Open Interest": ticker_data.get("open_interest", "N/A"),
                "Volume": ticker_data.get("volume", "N/A"),
                "Delta": ticker_data.get("greeks", {}).get("delta", "N/A"),
                "Gamma": ticker_data.get("greeks", {}).get("gamma", "N/A"),
                "Theta": ticker_data.get("greeks", {}).get("theta", "N/A"),
                "Vega": ticker_data.get("greeks", {}).get("vega", "N/A"),
                "IV": quotes.get("mark_iv", "N/A")
            }
            
            # Display in a clean table
            st.write("**🔍 Raw Values from API:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**💰 Pricing Data:**")
                st.write(f"- **Best Bid**: `{raw_data['Best Bid']}`")
                st.write(f"- **Best Ask**: `{raw_data['Best Ask']}`")
                st.write(f"- **Mark Price**: `{raw_data['Mark Price']}`")
                
                # Calculate mid if bid/ask available
                if raw_data['Best Bid'] and raw_data['Best Ask']:
                    try:
                        bid_val = float(raw_data['Best Bid'])
                        ask_val = float(raw_data['Best Ask'])
                        mid_val = (bid_val + ask_val) / 2
                        st.write(f"- **Mid Price**: `{mid_val}`")
                        st.write(f"- **Mid ÷ 10**: `{mid_val / 10:.2f}`")
                        st.write(f"- **Mid ÷ 100**: `{mid_val / 100:.4f}`")
                        st.write(f"- **Mid ÷ 1000**: `{mid_val / 1000:.6f}`")
                        st.write(f"- **Mid ÷ 10000**: `{mid_val / 10000:.6f}`")
                    except (ValueError, TypeError):
                        st.write("- **Mid Price**: Could not calculate")
            
            with col2:
                st.write("**📈 Greeks & Other:**")
                st.write(f"- **Open Interest**: `{raw_data['Open Interest']}`")
                st.write(f"- **Volume**: `{raw_data['Volume']}`")
                st.write(f"- **Delta**: `{raw_data['Delta']}`")
                st.write(f"- **IV**: `{raw_data['IV']}`")
            
            # Show complete raw JSON
            if st.checkbox(f"Show complete raw JSON for {symbol}"):
                st.json(ticker_data)
                
        else:
            st.error(f"❌ No ticker data for {symbol}")
            
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error fetching {symbol}: {e}")

# Step 3: Quick conversion test
st.subheader("Step 3: Quick Conversion Test")

expected_price = st.number_input("What should the option price be? (e.g., 0.50)", value=0.50, step=0.01)

if target_symbols and expected_price > 0:
    symbol = target_symbols[0]["symbol"]  # Use first symbol
    try:
        ticker_response = requests.get(f"{BASE_URL}/tickers/{symbol}", timeout=10)
        ticker_data = ticker_response.json().get("result", {})
        quotes = ticker_data.get("quotes", {})
        
        if quotes.get("best_bid") and quotes.get("best_ask"):
            bid = float(quotes["best_bid"])
            ask = float(quotes["best_ask"])
            mid = (bid + ask) / 2
            
            needed_divisor = mid / expected_price
            
            st.success(f"🎯 **SOLUTION FOUND!**")
            st.write(f"- Raw Mid Price: `{mid}`")
            st.write(f"- Expected Price: `${expected_price}`")
            st.write(f"- **Needed Divisor: `{needed_divisor:.0f}`**")
            st.write(f"- Test: `{mid} ÷ {needed_divisor:.0f} = ${mid/needed_divisor:.2f}`")
            
            st.code(f"""
# Use this in your code:
def get_mid_price(ticker_data):
    quotes = ticker_data.get("quotes", {{}})
    bid = float(quotes.get("best_bid", 0))
    ask = float(quotes.get("best_ask", 0))
    if bid and ask:
        mid = (bid + ask) / 2
        return mid / {needed_divisor:.0f}  # <-- Use this divisor
    return None
            """, language="python")
            
    except Exception as e:
        st.error(f"Conversion test failed: {e}")

# Step 4: Manual ticker lookup
st.subheader("Step 4: Manual Symbol Lookup")
manual_symbol = st.text_input("Enter exact symbol to test:", placeholder="C-BTC-128400-290825")

if manual_symbol and st.button("Fetch Manual Symbol"):
    try:
        response = requests.get(f"{BASE_URL}/tickers/{manual_symbol}")
        if response.status_code == 200:
            data = response.json().get("result", {})
            st.json(data)
        else:
            st.error(f"HTTP {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Error: {e}")
