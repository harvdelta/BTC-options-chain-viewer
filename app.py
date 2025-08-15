import streamlit as st
import requests

# ======================
# CONFIG
# ======================
BASE_URL = "https://api.delta.exchange/v2"

st.set_page_config(page_title="🎯 128400 Strike ONLY", layout="wide")
st.title("🎯 128400 Strike Data ONLY")

# Step 1: Find EXACTLY 128400 strike
st.subheader("Step 1: Finding EXACTLY 128400 Strike...")

try:
    products_response = requests.get(f"{BASE_URL}/products", timeout=10)
    products_response.raise_for_status()
    products = products_response.json().get("result", [])
    
    # Find EXACTLY 128400 strike
    exact_match = None
    for product in products:
        symbol = product.get("symbol", "")
        if symbol.startswith(("C-BTC", "P-BTC")):
            strike_price = product.get("strike_price")
            if str(strike_price) == "128400":  # EXACT match only
                exact_match = {
                    "symbol": symbol,
                    "strike_price": strike_price,
                    "product_id": product.get("id"),
                    "product": product
                }
                break  # Take first exact match and stop
    
    if exact_match:
        symbol = exact_match["symbol"]
        st.success(f"✅ Found EXACT match: **{symbol}** (Strike: {exact_match['strike_price']})")
    else:
        st.error("❌ No EXACT 128400 strike found")
        # Show nearby strikes for debugging
        nearby = []
        for product in products:
            s = product.get("symbol", "")
            if s.startswith(("C-BTC", "P-BTC")):
                sp = product.get("strike_price")
                try:
                    if 128000 <= float(sp) <= 129000:
                        nearby.append(f"{s} (Strike: {sp})")
                except:
                    pass
        if nearby:
            st.write("**Nearby strikes found:**")
            for n in nearby[:5]:
                st.write(f"- {n}")
        st.stop()

except requests.exceptions.RequestException as e:
    st.error(f"❌ Error: {e}")
    st.stop()

# Step 2: Get ticker data for THIS SYMBOL ONLY
st.subheader(f"Step 2: Raw Data for {symbol} ONLY")

try:
    ticker_response = requests.get(f"{BASE_URL}/tickers/{symbol}", timeout=10)
    ticker_response.raise_for_status()
    ticker_data = ticker_response.json().get("result", {})
    
    if ticker_data:
        quotes = ticker_data.get("quotes", {})
        
        # Extract ONLY the values we need
        bid = quotes.get("best_bid")
        ask = quotes.get("best_ask")
        mark = ticker_data.get("mark_price")
        oi = ticker_data.get("open_interest")
        volume = ticker_data.get("volume")
        
        # Greeks
        greeks = ticker_data.get("greeks", {})
        delta = greeks.get("delta")
        gamma = greeks.get("gamma")
        theta = greeks.get("theta")
        vega = greeks.get("vega")
        
        iv = quotes.get("mark_iv")
        
        st.success(f"✅ Got ticker data for {symbol}")
        
        # Display ONLY this data
        st.write("**📊 RAW VALUES FROM API:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Best Bid", bid if bid else "N/A")
            st.metric("Best Ask", ask if ask else "N/A") 
            st.metric("Mark Price", mark if mark else "N/A")
            
            # Calculate mid price
            if bid and ask:
                try:
                    mid = (float(bid) + float(ask)) / 2
                    st.metric("Mid Price", f"{mid:.2f}")
                except:
                    st.metric("Mid Price", "Error")
            else:
                st.metric("Mid Price", "N/A")
        
        with col2:
            st.metric("Open Interest", oi if oi else "N/A")
            st.metric("Volume", volume if volume else "N/A")
            st.metric("Delta", delta if delta else "N/A")
            st.metric("IV", iv if iv else "N/A")
        
        # Conversion test
        st.subheader("Step 3: Conversion Test")
        
        expected = st.number_input("Expected price ($):", value=0.50, step=0.01)
        
        if bid and ask and expected > 0:
            try:
                mid = (float(bid) + float(ask)) / 2
                divisor = mid / expected
                
                st.write("**🔍 CONVERSION ANALYSIS:**")
                st.write(f"- Raw Bid: `{bid}`")
                st.write(f"- Raw Ask: `{ask}`")  
                st.write(f"- Raw Mid: `{mid}`")
                st.write(f"- Expected: `${expected}`")
                st.write(f"- **NEEDED DIVISOR: `{divisor:.0f}`**")
                st.write(f"- **TEST: `{mid} ÷ {divisor:.0f} = ${mid/divisor:.4f}`**")
                
                # Show the exact code fix
                st.code(f"""
# EXACT FIX FOR YOUR CODE:
def get_mid_price(ticker_data):
    quotes = ticker_data.get("quotes", {{}})
    bid = quotes.get("best_bid")
    ask = quotes.get("best_ask")
    if bid and ask:
        mid = (float(bid) + float(ask)) / 2
        return mid / {divisor:.0f}  # <-- USE THIS EXACT NUMBER
    return None
""", language="python")
                
            except Exception as e:
                st.error(f"Calculation error: {e}")
        
        # Raw JSON if needed
        if st.checkbox("Show raw JSON"):
            st.json(ticker_data)
            
    else:
        st.error(f"❌ No ticker data for {symbol}")
        
except requests.exceptions.RequestException as e:
    st.error(f"❌ Error fetching ticker for {symbol}: {e}")
