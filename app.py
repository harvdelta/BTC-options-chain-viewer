import streamlit as st
import requests
import json

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"

st.set_page_config(page_title="🔍 Raw API Values Check", layout="wide")
st.title("🔍 Raw API Values for 128000 Strike")

# Step 1: Get all products
st.subheader("Step 1: Fetching Products...")

try:
    products_response = requests.get(f"{BASE_URL}/products", timeout=10)
    products_response.raise_for_status()
    products_data = products_response.json()
    products = products_data.get("result", [])
    
    st.success(f"✅ Fetched {len(products)} products")
    
    # Filter for BTC options near 128000 strike
    target_options = []
    for product in products:
        symbol = product.get("symbol", "")
        if symbol.startswith(("C-BTC", "P-BTC")):
            strike_price = product.get("strike_price")
            if strike_price:
                try:
                    strike_num = float(strike_price)
                    # Look for strikes around 128000 (allow some variation)
                    if 127000 <= strike_num <= 129000 or 1270000 <= strike_num <= 1290000 or 12700 <= strike_num <= 12900:
                        target_options.append(product)
                except ValueError:
                    pass
    
    st.write(f"Found {len(target_options)} options near 128000 strike:")
    
    if target_options:
        for i, option in enumerate(target_options[:5]):  # Show first 5
            st.write(f"**Option {i+1}:**")
            st.json({
                "symbol": option.get("symbol"),
                "strike_price": option.get("strike_price"),
                "strike_price_type": type(option.get("strike_price")).__name__,
                "raw_strike_value": repr(option.get("strike_price")),
            })
    else:
        st.warning("No options found near 128000. Let's see what strikes are available:")
        
        # Show all BTC option strikes
        btc_strikes = []
        for product in products:
            symbol = product.get("symbol", "")
            if symbol.startswith(("C-BTC", "P-BTC")):
                strike = product.get("strike_price")
                if strike:
                    btc_strikes.append(float(strike))
        
        if btc_strikes:
            btc_strikes = sorted(set(btc_strikes))
            st.write("**All BTC Option Strikes:**")
            for i, strike in enumerate(btc_strikes[:20]):  # Show first 20
                st.write(f"{i+1}. {strike}")
            if len(btc_strikes) > 20:
                st.write(f"... and {len(btc_strikes) - 20} more strikes")

except requests.exceptions.RequestException as e:
    st.error(f"❌ Error fetching products: {e}")
    st.stop()

# Step 2: Get ticker data for the target option
st.subheader("Step 2: Fetching Ticker Data...")

if target_options:
    # Use the first target option
    selected_option = target_options[0]
    symbol = selected_option["symbol"]
    
    st.write(f"**Analyzing symbol: {symbol}**")
    
    # Method 1: Get from bulk tickers
    st.write("**Method 1: Bulk Tickers API**")
    try:
        tickers_response = requests.get(f"{BASE_URL}/tickers", timeout=10)
        tickers_response.raise_for_status()
        tickers_data = tickers_response.json()
        all_tickers = tickers_data.get("result", [])
        
        # Find our symbol
        target_ticker = None
        for ticker in all_tickers:
            if ticker.get("symbol") == symbol:
                target_ticker = ticker
                break
        
        if target_ticker:
            st.success("✅ Found ticker in bulk data")
            st.write("**Raw Ticker Data:**")
            st.json({
                "symbol": target_ticker.get("symbol"),
                "quotes": target_ticker.get("quotes", {}),
                "mark_price": target_ticker.get("mark_price"),
                "mark_price_type": type(target_ticker.get("mark_price")).__name__,
                "underlying_asset": target_ticker.get("underlying_asset"),
                "full_ticker": target_ticker  # Show everything
            })
        else:
            st.warning("❌ Symbol not found in bulk ticker data")
            
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error fetching bulk tickers: {e}")
    
    # Method 2: Get individual ticker
    st.write("**Method 2: Individual Ticker API**")
    try:
        individual_response = requests.get(f"{BASE_URL}/tickers/{symbol}", timeout=10)
        individual_response.raise_for_status()
        individual_data = individual_response.json()
        individual_ticker = individual_data.get("result", {})
        
        if individual_ticker:
            st.success("✅ Found individual ticker data")
            st.write("**Raw Individual Ticker Data:**")
            st.json(individual_ticker)
        else:
            st.warning("❌ No individual ticker data")
            
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error fetching individual ticker: {e}")
    
    # Method 3: Try orderbook
    st.write("**Method 3: Order Book API**")
    try:
        orderbook_response = requests.get(f"{BASE_URL}/l2orderbook/{symbol}", timeout=10)
        if orderbook_response.status_code == 200:
            orderbook_data = orderbook_response.json()
            st.success("✅ Found orderbook data")
            st.write("**Raw Orderbook Data:**")
            st.json(orderbook_data)
        else:
            st.warning(f"❌ Orderbook API returned {orderbook_response.status_code}")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error fetching orderbook: {e}")
    
    # Step 3: Calculate what we're getting vs what we expect
    st.subheader("Step 3: Current Calculation Analysis")
    
    if target_ticker:
        quotes = target_ticker.get("quotes", {})
        bid = quotes.get("best_bid")
        ask = quotes.get("best_ask")
        mark = target_ticker.get("mark_price")
        
        st.write("**What we're extracting:**")
        st.write(f"- Raw Bid: {bid} (type: {type(bid).__name__})")
        st.write(f"- Raw Ask: {ask} (type: {type(ask).__name__})")
        st.write(f"- Raw Mark Price: {mark} (type: {type(mark).__name__})")
        
        if bid and ask:
            try:
                raw_mid = (float(bid) + float(ask)) / 2
                st.write(f"- **Calculated Mid: {raw_mid}**")
                st.write(f"- **Your Code Result: ${raw_mid / 10000:.4f}** (dividing by 10000)")
                st.write(f"- **Expected Result: $0.50**")
                st.write(f"- **Needed Divisor: {raw_mid / 0.5:.0f}**")
            except (ValueError, TypeError) as e:
                st.error(f"Error calculating mid: {e}")

else:
    st.warning("No target options found to analyze")

# Step 4: Raw JSON dump for manual inspection
st.subheader("Step 4: Raw JSON Dump")

if st.checkbox("Show complete raw product data"):
    if target_options:
        st.write("**Complete Product Data:**")
        st.text(json.dumps(target_options[0], indent=2))

if st.checkbox("Show complete raw ticker data"):
    if target_options and 'target_ticker' in locals() and target_ticker:
        st.write("**Complete Ticker Data:**")
        st.text(json.dumps(target_ticker, indent=2))
