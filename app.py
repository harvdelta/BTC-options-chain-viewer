import streamlit as st
import requests
import pandas as pd
import hashlib
import hmac
import time
import json
from datetime import datetime

# Try to import plotly, fallback to basic charts if not available
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Install with: pip install plotly")

# Page configuration
st.set_page_config(
    page_title="Delta Exchange Options Chain",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

class DeltaExchangeAPI:
    def __init__(self, api_key, api_secret, base_url="https://api.india.delta.exchange"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
    
    def _generate_signature(self, method, endpoint, payload=""):
        timestamp = str(int(time.time()))
        message = method + timestamp + endpoint + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp
    
    def _make_request(self, method, endpoint, params=None, data=None):
        url = f"{self.base_url}{endpoint}"
        payload = ""
        if method == "GET" and params:
            sorted_params = sorted(params.items())
            payload = "&".join([f"{k}={v}" for k, v in sorted_params])
        elif method == "POST" and data:
            payload = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        signature, timestamp = self._generate_signature(method, endpoint, payload)
        
        headers = {
            "api-key": self.api_key,
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"API request failed: {str(e)}")
            return None
    
    def get_products(self):
        return self._make_request("GET", "/v2/products")
    
    def get_tickers(self):
        return self._make_request("GET", "/v2/tickers")

@st.cache_data(ttl=300)
def fetch_options_data(api_key, api_secret, base_url):
    api = DeltaExchangeAPI(api_key, api_secret, base_url)
    products_response = api.get_products()
    if not products_response or 'result' not in products_response:
        return None, None, None
    
    products = products_response['result']
    tickers_response = api.get_tickers()
    ticker_data = {}
    if tickers_response and 'result' in tickers_response:
        for ticker in tickers_response['result']:
            ticker_data[ticker.get('symbol')] = ticker
    
    options = []
    for product in products:
        contract_type = product.get('contract_type', '')
        underlying_symbol = product.get('underlying_asset', {}).get('symbol', '')
        if contract_type in ['call_options', 'put_options'] and underlying_symbol == 'BTC':
            symbol = product.get('symbol')
            if symbol in ticker_data:
                product.update(ticker_data[symbol])
            options.append(product)
    
    if not options:
        return None, None, None
    
    underlying_groups = {}
    for option in options:
        underlying = option.get('underlying_asset', {}).get('symbol', 'Unknown')
        underlying_groups.setdefault(underlying, []).append(option)
    
    nearest_expiry_options = {}
    for underlying, opts in underlying_groups.items():
        if underlying == 'BTC':
            sorted_opts = sorted(opts, key=lambda x: x.get('settlement_time', '9999-12-31T23:59:59Z'))
            if sorted_opts:
                nearest_expiry = sorted_opts[0].get('settlement_time')
                nearest_expiry_options[underlying] = [
                    opt for opt in sorted_opts if opt.get('settlement_time') == nearest_expiry
                ]
    
    return options, underlying_groups, nearest_expiry_options

def create_options_chain_table(options_data, underlying):
    if underlying not in options_data:
        return None
    
    options = options_data[underlying]
    calls = [opt for opt in options if opt.get('contract_type') == 'call_options']
    puts = [opt for opt in options if opt.get('contract_type') == 'put_options']
    
    strikes = {}
    for call in calls:
        strike = call.get('strike_price', 0)
        strikes.setdefault(strike, {'call': None, 'put': None})['call'] = call
    for put in puts:
        strike = put.get('strike_price', 0)
        strikes.setdefault(strike, {'call': None, 'put': None})['put'] = put
    
    chain_data = []
    for strike in sorted(strikes.keys()):
        call_data = strikes[strike]['call']
        put_data = strikes[strike]['put']
        row = {
            'Strike': strike,
            'Call_Symbol': call_data.get('symbol', '') if call_data else '',
            'Call_Price': call_data.get('mark_price', 0) if call_data else 0,
            'Put_Symbol': put_data.get('symbol', '') if put_data else '',
            'Put_Price': put_data.get('mark_price', 0) if put_data else 0,
        }
        chain_data.append(row)
    
    return pd.DataFrame(chain_data)

def create_options_visualizations(df, underlying):
    if df is None or df.empty or not PLOTLY_AVAILABLE:
        return None, None
    
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df['Strike'], y=df['Call_Price'], name='Call Price', line=dict(color='green', width=3), mode='lines+markers'))
    fig1.add_trace(go.Scatter(x=df['Strike'], y=df['Put_Price'], name='Put Price', line=dict(color='red', width=3), mode='lines+markers'))
    fig1.update_layout(title=f'{underlying} Options Prices by Strike', xaxis_title='Strike Price', yaxis_title='Option Price (USD)', height=500, hovermode='x unified')
    
    df_clean = df[(df['Call_Price'] > 0) & (df['Put_Price'] > 0)].copy()
    if not df_clean.empty:
        df_clean['Call_Put_Spread'] = df_clean['Call_Price'] - df_clean['Put_Price']
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=df_clean['Strike'], y=df_clean['Call_Put_Spread'], name='Call-Put Spread', marker_color=['green' if x > 0 else 'red' for x in df_clean['Call_Put_Spread']], opacity=0.7))
        fig2.update_layout(title=f'{underlying} Call-Put Price Spread', xaxis_title='Strike Price', yaxis_title='Price Difference (Call - Put)', height=400)
    else:
        fig2 = None
    
    return fig1, fig2

def main():
    st.title("₿ BTC Options Chain Viewer")
    st.markdown("**Delta Exchange India - Bitcoin Options**")
    st.markdown("---")
    
    st.sidebar.header("Configuration")
    
    try:
        api_key = st.secrets["delta_exchange"]["api_key"]
        api_secret = st.secrets["delta_exchange"]["api_secret"]
        base_url = st.secrets["delta_exchange"].get("base_url", "https://api.india.delta.exchange")
    except Exception as e:
        st.error(f"Error loading API credentials: {str(e)}")
        st.stop()
    
    with st.spinner("Fetching BTC options data..."):
        all_options, underlying_groups, nearest_expiry_options = fetch_options_data(api_key, api_secret, base_url)
    
    if not nearest_expiry_options or 'BTC' not in nearest_expiry_options:
        st.error("No BTC options data available or API request failed.")
        st.stop()
    
    selected_underlying = 'BTC'
    if nearest_expiry_options[selected_underlying]:
        expiry_date = nearest_expiry_options[selected_underlying][0].get('settlement_time', 'Unknown')
        try:
            expiry_dt = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
            st.info(f"📅 Nearest Expiry: {expiry_dt.strftime('%Y-%m-%d %H:%M UTC')}")
        except:
            st.info(f"📅 Nearest Expiry: {expiry_date}")
    
    chain_df = create_options_chain_table(nearest_expiry_options, selected_underlying)
    
    if chain_df is not None and not chain_df.empty:
        # ✅ FIX: Ensure numeric types before comparisons
        for col in ['Call_Price', 'Put_Price']:
            chain_df[col] = pd.to_numeric(chain_df[col], errors='coerce').fillna(0)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Strikes", len(chain_df))
        with col2:
            st.metric("Active Calls", len(chain_df[chain_df['Call_Price'] > 0]))
        with col3:
            st.metric("Active Puts", len(chain_df[chain_df['Put_Price'] > 0]))
        with col4:
            avg_call_price = chain_df[chain_df['Call_Price'] > 0]['Call_Price'].mean()
            st.metric("Avg Call Price", f"${avg_call_price:.2f}" if not pd.isna(avg_call_price) else "N/A")
        
        display_df = chain_df.copy().round(4)
        st.dataframe(display_df, use_container_width=True)
        
        if PLOTLY_AVAILABLE:
            fig1, fig2 = create_options_visualizations(chain_df, selected_underlying)
            if fig1: st.plotly_chart(fig1, use_container_width=True)
            if fig2: st.plotly_chart(fig2, use_container_width=True)
    
    else:
        st.warning("No BTC options data available for nearest expiry")

if __name__ == "__main__":
    main()
