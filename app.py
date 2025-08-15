import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz

# ======================
# CONFIG
# ======================
# Corrected API base URL from official documentation
BASE_URL = "https://publicapi.deltaexchange.io/v1"
IST = pytz.timezone("Asia/Kolkata")

# ======================
# UTILS
# ======================
def fetch_market_status():
    """Fetch market status from Delta Exchange."""
    try:
        r = requests.get(f"{BASE_URL}/market-status")
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching market status: {e}")
        return None

def fetch_tickers():
    """Fetch all tickers from Delta Exchange."""
    try:
        r = requests.get(f"{BASE_URL}/tickers")
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching tickers: {e}")
        return None

def filter_btc_options(market_data):
    """Filter BTC options from market data."""
    if not market_data or 'markets' not in market_data:
        return []
    
    btc_options = []
    for market in market_data['markets']:
        symbol = market.get('baseMarket', '') + market.get('quoteMarket', '')
        # Look for BTC options patterns - this might need adjustment based on actual data
        if ('BTC' in symbol and 
            market.get('type', '') in ['OPTIONS', 'OPTION'] or
            'CALL' in symbol or 'PUT' in symbol or
            'C-' in symbol or 'P-' in symbol):
            btc_options.append(market)
    
    return btc_options

def parse_option_symbol(symbol):
    """Parse option symbol to extract type, strike, and expiry."""
    # This function needs to be adjusted based on actual symbol format
    # Common formats: BTC-25DEC20-18000-C, C-BTC-18000-25DEC20, etc.
    try:
        parts = symbol.split('-')
        if len(parts) >= 4:
            if parts[0] in ['C', 'P']:  # Call or Put prefix
                option_type = 'CALL' if parts[0] == 'C' else 'PUT'
                asset = parts[1]
                strike = float(parts[2])
                expiry = parts[3]
            elif parts[-1] in ['C', 'P']:  # Call or Put suffix
                asset = parts[0]
                expiry = parts[1]
                strike = float(parts[2])
                option_type = 'CALL' if parts[-1] == 'C' else 'PUT'
            else:
                return None, None, None, None
            return asset, option_type, strike, expiry
    except (ValueError, IndexError):
        pass
    return None, None, None, None

# ======================
# STREAMLIT UI
# ======================
st.set_page_config(page_title="BTC Options Chain Viewer", layout="wide")
st.title("₿ BTC Options Chain Viewer")

# Add debugging information
st.subheader("API Status Check")

# Fetch market status
market_data = fetch_market_status()
if market_data is None:
    st.error("Failed to fetch market data from Delta Exchange API")
    st.stop()

# Display some debug info
st.write(f"Total markets found: {len(market_data.get('markets', []))}")

# Show sample of available markets for debugging
if market_data.get('markets'):
    sample_markets = market_data['markets'][:10]
    st.write("Sample markets:")
    for market in sample_markets:
        st.write(f"- {market.get('baseMarket', 'N/A')}/{market.get('quoteMarket', 'N/A')} (Type: {market.get('type', 'N/A')})")

# Filter BTC options
btc_options = filter_btc_options(market_data)
st.write(f"BTC Options found: {len(btc_options)}")

if not btc_options:
    st.warning("No BTC options found. This might be because:")
    st.write("1. Delta Exchange might not offer BTC options through this API endpoint")
    st.write("2. The symbol format might be different than expected")
    st.write("3. Options might be available on a different API version")
    
    st.subheader("Available Markets by Type")
    if market_data.get('markets'):
        market_types = {}
        for market in market_data['markets']:
            market_type = market.get('type', 'UNKNOWN')
            if market_type not in market_types:
                market_types[market_type] = []
            market_types[market_type].append(f"{market.get('baseMarket', 'N/A')}/{market.get('quoteMarket', 'N/A')}")
        
        for market_type, markets in market_types.items():
            st.write(f"**{market_type}**: {len(markets)} markets")
            if len(markets) <= 5:
                for market in markets:
                    st.write(f"  - {market}")
            else:
                for market in markets[:5]:
                    st.write(f"  - {market}")
                st.write(f"  ... and {len(markets) - 5} more")
    
    st.stop()

# If we found BTC options, continue with the original logic
st.subheader("BTC Options Processing")

# Fetch ticker data
ticker_data = fetch_tickers()
if ticker_data is None:
    st.error("Failed to fetch ticker data")
    st.stop()

# Process options data
calls = []
puts = []

for option in btc_options:
    symbol = option.get('baseMarket', '') + option.get('quoteMarket', '')
    asset, option_type, strike, expiry = parse_option_symbol(symbol)
    
    if asset != 'BTC' or strike is None:
        continue
    
    # Get ticker information
    ticker_info = ticker_data.get(symbol, {})
    bid = ticker_info.get('buy')
    ask = ticker_info.get('sell')
    
    if bid is not None and ask is not None:
        try:
            mid_price = (float(bid) + float(ask)) / 2
            
            if option_type == 'CALL':
                calls.append({
                    "Strike": strike,
                    "Call Mid Price": mid_price,
                    "Expiry": expiry,
                    "Symbol": symbol
                })
            elif option_type == 'PUT':
                puts.append({
                    "Strike": strike,
                    "Put Mid Price": mid_price,
                    "Expiry": expiry,
                    "Symbol": symbol
                })
        except (ValueError, TypeError):
            continue

# Create DataFrames
if calls or puts:
    df_calls = pd.DataFrame(calls).sort_values(by="Strike") if calls else pd.DataFrame()
    df_puts = pd.DataFrame(puts).sort_values(by="Strike") if puts else pd.DataFrame()
    
    if not df_calls.empty and not df_puts.empty:
        df = pd.merge(df_calls[['Strike', 'Call Mid Price']], 
                     df_puts[['Strike', 'Put Mid Price']], 
                     on="Strike", how="outer").sort_values(by="Strike").reset_index(drop=True)
    elif not df_calls.empty:
        df = df_calls[['Strike', 'Call Mid Price']].sort_values(by="Strike").reset_index(drop=True)
    else:
        df = df_puts[['Strike', 'Put Mid Price']].sort_values(by="Strike").reset_index(drop=True)
    
    st.subheader("Options Chain")
    st.dataframe(df, use_container_width=True)
    
    # Show raw data for debugging
    if st.checkbox("Show raw options data"):
        st.write("Calls:", calls)
        st.write("Puts:", puts)
else:
    st.warning("No valid options data found with pricing information")
