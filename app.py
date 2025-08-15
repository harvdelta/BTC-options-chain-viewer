import streamlit as st
import requests
import pandas as pd
import hashlib
import hmac
import time
import json
from datetime import datetime, timedelta

# Try to import plotly, fallback to basic charts if not available
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
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
        
        # Prepare payload for signature
        payload = ""
        if method == "GET" and params:
            # Sort parameters for consistent signature
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
        """Get all available products"""
        return self._make_request("GET", "/v2/products")
    
    def get_orderbook(self, symbol):
        """Get orderbook for a specific symbol"""
        return self._make_request("GET", f"/v2/l2orderbook/{symbol}")
    
    def get_ticker(self, symbol):
        """Get ticker data for a specific symbol"""
        return self._make_request("GET", f"/v2/tickers/{symbol}")
    
    def get_tickers(self):
        """Get ticker data for all symbols"""
        return self._make_request("GET", "/v2/tickers")

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_options_data(api_key, api_secret, base_url):
    """Fetch and process options data"""
    api = DeltaExchangeAPI(api_key, api_secret, base_url)
    
    # Get all products
    products_response = api.get_products()
    if not products_response or 'result' not in products_response:
        return None, None, None
    
    products = products_response['result']
    
    # Get all tickers for pricing data
    tickers_response = api.get_tickers()
    ticker_data = {}
    if tickers_response and 'result' in tickers_response:
        for ticker in tickers_response['result']:
            ticker_data[ticker.get('symbol')] = ticker
    
    # Filter BTC options contracts only
    options = []
    for product in products:
        contract_type = product.get('contract_type', '')
        underlying_symbol = product.get('underlying_asset', {}).get('symbol', '')
        
        # Only include BTC options
        if contract_type in ['call_options', 'put_options'] and underlying_symbol == 'BTC':
            # Merge ticker data if available
            symbol = product.get('symbol')
            if symbol in ticker_data:
                product.update(ticker_data[symbol])
            options.append(product)
    
    if not options:
        return None, None, None
    
    # Group by underlying asset and find nearest expiry (BTC only now)
    underlying_groups = {}
    for option in options:
        underlying = option.get('underlying_asset', {}).get('symbol', 'Unknown')
        if underlying not in underlying_groups:
            underlying_groups[underlying] = []
        underlying_groups[underlying].append(option)
    
    # Find nearest expiry for BTC
    nearest_expiry_options = {}
    for underlying, opts in underlying_groups.items():
        if underlying == 'BTC':  # Only process BTC
            # Sort by settlement time to find nearest expiry
            sorted_opts = sorted(opts, key=lambda x: x.get('settlement_time', '9999-12-31T23:59:59Z'))
            if sorted_opts:
                nearest_expiry = sorted_opts[0].get('settlement_time')
                nearest_expiry_options[underlying] = [
                    opt for opt in sorted_opts 
                    if opt.get('settlement_time') == nearest_expiry
                ]
    
    return options, underlying_groups, nearest_expiry_options

def create_options_chain_table(options_data, underlying):
    """Create options chain table for display"""
    if underlying not in options_data:
        return None
    
    options = options_data[underlying]
    
    # Separate calls and puts
    calls = [opt for opt in options if opt.get('contract_type') == 'call_options']
    puts = [opt for opt in options if opt.get('contract_type') == 'put_options']
    
    # Group by strike price
    strikes = {}
    
    for call in calls:
        strike = call.get('strike_price', 0)
        if strike not in strikes:
            strikes[strike] = {'call': None, 'put': None}
        strikes[strike]['call'] = call
    
    for put in puts:
        strike = put.get('strike_price', 0)
        if strike not in strikes:
            strikes[strike] = {'call': None, 'put': None}
        strikes[strike]['put'] = put
    
    # Create DataFrame
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
    """Create visualizations for options data"""
    if df is None or df.empty or not PLOTLY_AVAILABLE:
        return None, None
    
    # Options Price Comparison
    fig1 = go.Figure()
    
    # Call and Put Prices
    fig1.add_trace(go.Scatter(
        x=df['Strike'], 
        y=df['Call_Price'], 
        name='Call Price', 
        line=dict(color='green', width=3),
        mode='lines+markers'
    ))
    
    fig1.add_trace(go.Scatter(
        x=df['Strike'], 
        y=df['Put_Price'], 
        name='Put Price', 
        line=dict(color='red', width=3),
        mode='lines+markers'
    ))
    
    fig1.update_layout(
        title=f'{underlying} Options Prices by Strike',
        xaxis_title='Strike Price',
        yaxis_title='Option Price (USD)',
        height=500,
        showlegend=True,
        hovermode='x unified'
    )
    
    # Price spread analysis
    df_clean = df[(df['Call_Price'] > 0) & (df['Put_Price'] > 0)].copy()
    if not df_clean.empty:
        df_clean['Call_Put_Spread'] = df_clean['Call_Price'] - df_clean['Put_Price']
        
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df_clean['Strike'],
            y=df_clean['Call_Put_Spread'],
            name='Call-Put Spread',
            marker_color=['green' if x > 0 else 'red' for x in df_clean['Call_Put_Spread']],
            opacity=0.7
        ))
        
        fig2.update_layout(
            title=f'{underlying} Call-Put Price Spread',
            xaxis_title='Strike Price',
            yaxis_title='Price Difference (Call - Put)',
            height=400
        )
    else:
        fig2 = None
    
    return fig1, fig2

def create_basic_charts(df, underlying):
    """Create basic charts using Streamlit's built-in charting when Plotly is not available"""
    if df is None or df.empty:
        return
    
    st.subheader("BTC Options Price Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Call Prices**")
        price_df = df[['Strike', 'Call_Price']].set_index('Strike')
        st.line_chart(price_df)
    
    with col2:
        st.write("**Put Prices**")
        price_df = df[['Strike', 'Put_Price']].set_index('Strike')
        st.line_chart(price_df)

def main():
    st.title("₿ BTC Options Chain Viewer")
    st.markdown("**Delta Exchange India - Bitcoin Options**")
    st.markdown("---")
    
    # Sidebar for configuration
    st.sidebar.header("Configuration")
    
    # Get API credentials from secrets
    try:
        api_key = st.secrets["delta_exchange"]["api_key"]
        api_secret = st.secrets["delta_exchange"]["api_secret"]
        base_url = st.secrets["delta_exchange"].get("base_url", "https://api.india.delta.exchange")
        
        if not api_key or not api_secret:
            st.error("API credentials not found in secrets. Please check your Streamlit secrets configuration.")
            st.stop()
            
    except Exception as e:
        st.error(f"Error loading API credentials: {str(e)}")
        st.markdown("""
        Please ensure your Streamlit secrets are configured with:
        ```toml
        [delta_exchange]
        api_key = "LkxpWQGihtxtBUJfCGx1uSTpvyIqQl"
        api_secret = "aG9aklujDrFK8nPZMyo6UJr6wsAyTDf3tEjM3bz5s1QtN3Cm2Q0OYqRd3cGl"
        base_url = "https://api.india.delta.exchange"
        ```
        """)
        st.stop()
    
    # Fetch BTC options data
    with st.spinner("Fetching BTC options data from Delta Exchange India..."):
        all_options, underlying_groups, nearest_expiry_options = fetch_options_data(api_key, api_secret, base_url)
    
    if not nearest_expiry_options or 'BTC' not in nearest_expiry_options:
        st.error("No BTC options data available or API request failed.")
        st.info("Make sure BTC options are available on Delta Exchange India.")
        st.stop()
    
    # Display BTC options chain
    selected_underlying = 'BTC'  # Fixed to BTC only
    st.subheader(f"Options Chain for Bitcoin (BTC)")
    
    # Get expiry date
    if nearest_expiry_options[selected_underlying]:
        expiry_date = nearest_expiry_options[selected_underlying][0].get('settlement_time', 'Unknown')
        try:
            # Parse and format the date
            expiry_dt = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
            formatted_expiry = expiry_dt.strftime('%Y-%m-%d %H:%M UTC')
            st.info(f"📅 Nearest Expiry: {formatted_expiry}")
        except:
            st.info(f"📅 Nearest Expiry: {expiry_date}")
    
    # Create and display options chain table
    chain_df = create_options_chain_table(nearest_expiry_options, selected_underlying)
    
    if chain_df is not None and not chain_df.empty:
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Strikes", len(chain_df))
        
        with col2:
            active_calls = len(chain_df[chain_df['Call_Price'] > 0])
            st.metric("Active Calls", active_calls)
        
        with col3:
            active_puts = len(chain_df[chain_df['Put_Price'] > 0])
            st.metric("Active Puts", active_puts)
        
        with col4:
            avg_call_price = chain_df[chain_df['Call_Price'] > 0]['Call_Price'].mean()
            st.metric("Avg Call Price", f"${avg_call_price:.2f}" if not pd.isna(avg_call_price) else "N/A")
        
        # Display the BTC options chain table
        st.subheader("BTC Options Chain Data")
        
        # Format the dataframe for better display
        display_df = chain_df.copy()
        display_df = display_df.round(4)
        
        # Color code the table
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                "Strike": st.column_config.NumberColumn("Strike Price ($)", format="%.0f"),
                "Call_Symbol": st.column_config.TextColumn("Call Symbol", width="medium"),
                "Call_Price": st.column_config.NumberColumn("Call Price ($)", format="%.4f"),
                "Put_Symbol": st.column_config.TextColumn("Put Symbol", width="medium"),
                "Put_Price": st.column_config.NumberColumn("Put Price ($)", format="%.4f"),
            }
        )
        
        # Create visualizations
        st.subheader("BTC Options Analysis")
        
        if PLOTLY_AVAILABLE:
            fig1, fig2 = create_options_visualizations(chain_df, selected_underlying)
            
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
            
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
        else:
            create_basic_charts(chain_df, selected_underlying)
        
        # Additional analysis
        st.subheader("Key Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Call Options Summary:**")
            call_stats = {
                "Active Strikes": len(chain_df[chain_df['Call_Price'] > 0]),
                "Avg Call Price": f"${chain_df[chain_df['Call_Price'] > 0]['Call_Price'].mean():.4f}" if len(chain_df[chain_df['Call_Price'] > 0]) > 0 else "N/A",
                "Highest Call Price": f"${chain_df['Call_Price'].max():.4f}" if chain_df['Call_Price'].max() > 0 else "N/A",
                "Lowest Strike (ITM)": f"${chain_df[chain_df['Call_Price'] > 0]['Strike'].min():.0f}" if len(chain_df[chain_df['Call_Price'] > 0]) > 0 else "N/A"
            }
            for key, value in call_stats.items():
                st.write(f"- {key}: {value}")
        
        with col2:
            st.write("**Put Options Summary:**")
            put_stats = {
                "Active Strikes": len(chain_df[chain_df['Put_Price'] > 0]),
                "Avg Put Price": f"${chain_df[chain_df['Put_Price'] > 0]['Put_Price'].mean():.4f}" if len(chain_df[chain_df['Put_Price'] > 0]) > 0 else "N/A",
                "Highest Put Price": f"${chain_df['Put_Price'].max():.4f}" if chain_df['Put_Price'].max() > 0 else "N/A",
                "Highest Strike (ITM)": f"${chain_df[chain_df['Put_Price'] > 0]['Strike'].max():.0f}" if len(chain_df[chain_df['Put_Price'] > 0]) > 0 else "N/A"
            }
            for key, value in put_stats.items():
                st.write(f"- {key}: {value}")
    
    else:
        st.warning(f"No BTC options data available for nearest expiry")
        
        # Show what underlyings are available
        if underlying_groups:
            available_underlyings = list(underlying_groups.keys())
            st.info(f"Available underlying assets: {', '.join(available_underlyings)}")
    
    # Sidebar information
    st.sidebar.header("📊 BTC Options Info")
    st.sidebar.info("""
    This dashboard shows Bitcoin (BTC) options with the nearest expiry date from Delta Exchange India.
    
    **Features:**
    - Real-time option prices
    - Call and Put options side by side
    - Strike price analysis
    - Price spread visualization
    """)
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>BTC Options Chain Dashboard | Delta Exchange India | Data refreshes every 5 minutes</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
