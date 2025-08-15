import streamlit as st
import requests

st.title("🎯 ONLY 128400 Strike Data")

# Direct symbol test - try common symbol formats for 128400
possible_symbols = [
    "C-BTC-128400-290825",
    "P-BTC-128400-290825", 
    "C-BTC-128400-300825",
    "P-BTC-128400-300825",
    "C-BTC-128400-060925",
    "P-BTC-128400-060925"
]

st.write("Testing these exact symbols for 128400 strike:")
for symbol in possible_symbols:
    st.write(f"- {symbol}")

# Test each symbol
for symbol in possible_symbols:
    st.subheader(f"Testing: {symbol}")
    
    try:
        response = requests.get(f"https://api.delta.exchange/v2/tickers/{symbol}", timeout=5)
        
        if response.status_code == 200:
            data = response.json().get("result", {})
            quotes = data.get("quotes", {})
            
            bid = quotes.get("best_bid")
            ask = quotes.get("best_ask") 
            mark = data.get("mark_price")
            
            if bid and ask:
                mid = (float(bid) + float(ask)) / 2
                
                st.success(f"✅ FOUND DATA for {symbol}")
                st.write(f"**Bid:** {bid}")
                st.write(f"**Ask:** {ask}")
                st.write(f"**Mid:** {mid}")
                st.write(f"**Mark:** {mark}")
                
                # Calculate divisor for $0.50
                divisor = mid / 0.5
                st.write(f"**To get $0.50, divide by: {divisor:.0f}**")
                st.write(f"**Test: {mid} ÷ {divisor:.0f} = ${mid/divisor:.2f}**")
                
                break  # STOP after finding first working symbol
            else:
                st.warning(f"No bid/ask for {symbol}")
                
        else:
            st.error(f"HTTP {response.status_code} for {symbol}")
            
    except Exception as e:
        st.error(f"Error with {symbol}: {e}")

# Manual input if none work
st.subheader("Manual Symbol Input")
manual_symbol = st.text_input("Enter exact 128400 strike symbol:")

if manual_symbol:
    try:
        response = requests.get(f"https://api.delta.exchange/v2/tickers/{manual_symbol}")
        if response.status_code == 200:
            data = response.json().get("result", {})
            quotes = data.get("quotes", {})
            
            st.write(f"**Raw data for {manual_symbol}:**")
            st.write(f"Bid: {quotes.get('best_bid')}")
            st.write(f"Ask: {quotes.get('best_ask')}")
            st.write(f"Mark: {data.get('mark_price')}")
            
        else:
            st.error(f"Failed: {response.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")
