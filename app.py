import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"
IST = pytz.timezone("Asia/Kolkata")

# Cache for API responses
@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_products():
    """Fetch all products from Delta Exchange with caching."""
    try:
        response = requests.get(f"{BASE_URL}/products", timeout=10)
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching products: {e}")
        return []

@st.cache_data(ttl=10)  # Cache tickers for 10 seconds
def fetch_all_tickers():
    """Fetch all tickers in one API call."""
    try:
        response = requests.get(f"{BASE_URL}/tickers", timeout=10)
        response.raise_for_status()
        data = response.json().get("result", [])
        # Convert to dict for faster lookup
        return {ticker["symbol"]: ticker for ticker in data}
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching tickers: {e}")
        return {}

def filter_btc_options_fast(products):
    """Fast filter for BTC options using regex."""
    btc_pattern = re.compile(r'^[CP]-BTC-')
    return [p for p in products if btc_pattern.match(p.get("symbol", ""))]

def parse_option_details(products):
    """Parse option details from products list."""
    options = []
    for product in products:
        symbol = product.get("symbol", "")
        if not symbol:
            continue
            
        # Parse symbol: C-BTC-114400-180825
        parts = symbol.split("-")
        if len(parts) >= 4:
            option_type = "CALL" if parts[0] == "C" else "PUT"
            
            # Use strike_price from product data (already in USD)
            strike = float(product.get("strike_price", 0))
            
            expiry_str = parts[3]
            settlement_time = product.get("settlement_time")
            
            options.append({
                "symbol": symbol,
                "type": option_type,
                "strike": strike,
                "expiry_str": expiry_str,
                "settlement_time": settlement_time,
                "product_id": product.get("id")
            })
    
    return options

def get_mid_price(ticker_data):
    """Calculate mid price from ticker data."""
    quotes = ticker_data.get("quotes", {})
    bid = quotes.get("best_bid")
    ask = quotes.get("best_ask")
    
    if bid and ask:
        try:
            mid = (float(bid) + float(ask)) / 2
            # Convert from Delta's price unit to USD
            # Based on the data, prices appear to be in a smaller unit
            # Typical conversion: divide by 100 (from cents to dollars)
            return mid / 100
        except (ValueError, TypeError):
            pass
    return None

def find_nearest_expiry(options):
    """Find the nearest expiry date."""
    if not options:
        return None, []
    
    # Get unique settlement times and sort
    settlement_times = sorted(set(opt["settlement_time"] for opt in options if opt["settlement_time"]))
    
    if not settlement_times:
        return None, []
    
    nearest_settlement = settlement_times[0]
    nearest_expiry_dt = datetime.fromisoformat(nearest_settlement.replace("Z", "+00:00")).astimezone(IST)
    nearest_options = [opt for opt in options if opt["settlement_time"] == nearest_settlement]
    
    return nearest_expiry_dt, nearest_options

# ======================
# STREAMLIT UI
# ======================
st.set_page_config(page_title="⚡ Fast BTC Options Viewer", layout="wide")
st.title("⚡ Fast BTC Options Chain Viewer")

# Create columns for layout
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

with col1:
    st.write("*Data refreshes automatically every 30 seconds*")

# Show loading spinner
with st.spinner("Loading BTC options data..."):
    
    # Step 1: Fetch all products (cached)
    products = fetch_products()
    if not products:
        st.error("Failed to fetch products data")
        st.stop()
    
    # Step 2: Filter BTC options (fast regex filter)
    btc_options_products = filter_btc_options_fast(products)
    
    if not btc_options_products:
        st.error("No BTC options found")
        st.info("Available product symbols (first 10):")
        for product in products[:10]:
            st.write(f"- {product.get('symbol', 'N/A')}")
        st.stop()
    
    # Step 3: Parse option details
    options = parse_option_details(btc_options_products)
    
    # Step 4: Find nearest expiry
    nearest_expiry_dt, nearest_options = find_nearest_expiry(options)
    
    if not nearest_expiry_dt or not nearest_options:
        st.error("No valid expiry data found")
        st.stop()
    
    # Step 5: Fetch all tickers in one call (cached)
    all_tickers = fetch_all_tickers()

# Display expiry info
st.subheader(f"📅 Nearest Expiry: {nearest_expiry_dt.strftime('%d %b %Y %I:%M %p IST')}")

# Process options data
calls_data = []
puts_data = []

for option in nearest_options:
    symbol = option["symbol"]
    strike = option["strike"]
    option_type = option["type"]
    
    # Get ticker data from our cached dictionary
    ticker_data = all_tickers.get(symbol)
    if not ticker_data:
        continue
    
    mid_price = get_mid_price(ticker_data)
    if mid_price is None:
        continue
    
    option_data = {
        "Strike": strike,
        "Mid Price": f"${mid_price:.2f}",
        "Mid Price (num)": mid_price,  # For sorting
        "Symbol": symbol
    }
    
    if option_type == "CALL":
        calls_data.append({**option_data, "Call Mid": f"${mid_price:.2f}"})
    else:
        puts_data.append({**option_data, "Put Mid": f"${mid_price:.2f}"})

# Create and display the options chain
if calls_data or puts_data:
    # Convert to DataFrames
    df_calls = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
    df_puts = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()
    
    # Merge calls and puts
    if not df_calls.empty and not df_puts.empty:
        df_calls_clean = df_calls[["Strike", "Call Mid"]].sort_values("Strike")
        df_puts_clean = df_puts[["Strike", "Put Mid"]].sort_values("Strike")
        df = pd.merge(df_calls_clean, df_puts_clean, on="Strike", how="outer")
    elif not df_calls.empty:
        df = df_calls[["Strike", "Call Mid"]].sort_values("Strike")
    else:
        df = df_puts[["Strike", "Put Mid"]].sort_values("Strike")
    
    df = df.sort_values("Strike").reset_index(drop=True)
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Strikes", len(df))
    with col2:
        st.metric("Call Options", len(calls_data))
    with col3:
        st.metric("Put Options", len(puts_data))
    
    # Display the options chain
    st.subheader("📊 Options Chain")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Strike": st.column_config.NumberColumn(
                "Strike Price",
                format="$%.0f"
            ),
            "Call Mid": st.column_config.TextColumn("Call Mid Price"),
            "Put Mid": st.column_config.TextColumn("Put Mid Price"),
        }
    )
    
    # Additional info
    with st.expander("ℹ️ Additional Information"):
        st.write(f"**Total BTC Options Found:** {len(btc_options_products)}")
        st.write(f"**Options for Nearest Expiry:** {len(nearest_options)}")
        st.write(f"**Last Updated:** {datetime.now(IST).strftime('%H:%M:%S IST')}")
        
        # Debug section to see raw data
        if st.checkbox("🔧 Show raw data for debugging"):
            st.write("**Sample product data:**")
            if btc_options_products:
                sample_product = btc_options_products[0]
                st.json({
                    "symbol": sample_product.get("symbol"),
                    "strike_price": sample_product.get("strike_price"),
                    "tick_size": sample_product.get("tick_size"),
                    "contract_value": sample_product.get("contract_value"),
                    "contract_unit_currency": sample_product.get("contract_unit_currency"),
                    "settling_asset": sample_product.get("settling_asset")
                })
            
            st.write("**Sample ticker data:**")
            if nearest_options and all_tickers:
                sample_symbol = nearest_options[0]["symbol"]
                sample_ticker = all_tickers.get(sample_symbol)
                if sample_ticker:
                    st.json({
                        "symbol": sample_ticker.get("symbol"),
                        "quotes": sample_ticker.get("quotes", {}),
                        "mark_price": sample_ticker.get("mark_price"),
                        "underlying_asset": sample_ticker.get("underlying_asset")
                    })
        
        if st.checkbox("Show all available expiries"):
            all_expiries = sorted(set(opt["expiry_str"] for opt in options))
            st.write("**Available Expiries:**")
            for exp in all_expiries[:10]:  # Show first 10
                st.write(f"- {exp}")
            if len(all_expiries) > 10:
                st.write(f"... and {len(all_expiries) - 10} more")

else:
    st.warning("No options data available with valid pricing")
    st.info(f"Found {len(nearest_options)} options for nearest expiry, but none had valid bid/ask prices")
