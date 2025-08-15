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

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_options_data(api_key, api_secret, base_url):
    """Fetch and process options data"""
    api = DeltaExchangeAPI(api_key, api_secret, base_url)
    
    # Get all products
    products_response = api.get_products()
    if not products_response or 'result' not in products_response:
        return None, None, None
    
    products = products_response['result']
    
    # Filter options contracts
    options = []
    for product in products:
        if product.get('product_type') == 'options':
            options.append(product)
    
    if not options:
        return None, None, None
    
    # Group by underlying asset and find nearest expiry
    underlying_groups = {}
    for option in options:
        underlying = option.get('underlying_asset', {}).get('symbol', 'Unknown')
        if underlying not in underlying_groups:
            underlying_groups[underlying] = []
        underlying_groups[underlying].append(option)
    
    # Find nearest expiry for each underlying
    nearest_expiry_options = {}
    for underlying, opts in underlying_groups.items():
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
    calls = [opt for opt in options if opt.get('option_type') == 'call_european']
    puts = [opt for opt in options if opt.get('option_type') == 'put_european']
    
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
            'Call_Volume': call_data.get('volume_24h', 0) if call_data else 0,
            'Call_OI': call_data.get('open_interest', 0) if call_data else 0,
            'Put_Symbol': put_data.get('symbol', '') if put_data else '',
            'Put_Price': put_data.get('mark_price', 0) if put_data else 0,
            'Put_Volume': put_data.get('volume_24h', 0) if put_data else 0,
            'Put_OI': put_data.get('open_interest', 0) if put_data else 0,
        }
        chain_data.append(row)
    
    return pd.DataFrame(chain_data)

def create_options_visualizations(df, underlying):
    """Create visualizations for options data"""
    if df is None or df.empty or not PLOTLY_AVAILABLE:
        return None, None
    
    # Options Chain Visualization
    fig1 = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Call Prices', 'Put Prices', 'Call Open Interest', 'Put Open Interest'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Call and Put Prices
    fig1.add_trace(
        go.Scatter(x=df['Strike'], y=df['Call_Price'], name='Call Price', line=dict(color='green')),
        row=1, col=1
    )
    
    fig1.add_trace(
        go.Scatter(x=df['Strike'], y=df['Put_Price'], name='Put Price', line=dict(color='red')),
        row=1, col=2
    )
    
    # Open Interest
    fig1.add_trace(
        go.Bar(x=df['Strike'], y=df['Call_OI'], name='Call OI', marker_color='lightgreen'),
        row=2, col=1
    )
    
    fig1.add_trace(
        go.Bar(x=df['Strike'], y=df['Put_OI'], name='Put OI', marker_color='lightcoral'),
        row=2, col=2
    )
    
    fig1.update_layout(
        title=f'{underlying} Options Chain Analysis',
        height=600,
        showlegend=True
    )
    
    # Volume Analysis
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=df['Strike'],
        y=df['Call_Volume'],
        name='Call Volume',
        marker_color='green',
        opacity=0.7
    ))
    
    fig2.add_trace(go.Bar(
        x=df['Strike'],
        y=df['Put_Volume'],
        name='Put Volume',
        marker_color='red',
        opacity=0.7
    ))
    
    fig2.update_layout(
        title=f'{underlying} Options Volume by Strike',
        xaxis_title='Strike Price',
        yaxis_title='24h Volume',
        barmode='group',
        height=400
    )
    
    return fig1, fig2

def create_basic_charts(df, underlying):
    """Create basic charts using Streamlit's built-in charting when Plotly is not available"""
    if df is None or df.empty:
        return
    
    st.subheader("Options Price Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Call Prices**")
        price_df = df[['Strike', 'Call_Price']].set_index('Strike')
        st.line_chart(price_df)
    
    with col2:
        st.write("**Put Prices**")
        price_df = df[['Strike', 'Put_Price']].set_index('Strike')
        st.line_chart(price_df)
    
    st.subheader("Open Interest Analysis")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.write("**Call Open Interest**")
        oi_df = df[['Strike', 'Call_OI']].set_index('Strike')
        st.bar_chart(oi_df)
    
    with col4:
        st.write("**Put Open Interest**")
        oi_df = df[['Strike', 'Put_OI']].set_index('Strike')
        st.bar_chart(oi_df)

def main():
    st.title("📊 Delta Exchange Options Chain")
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
    
    # Fetch data
    with st.spinner("Fetching options data from Delta Exchange India..."):
        all_options, underlying_groups, nearest_expiry_options = fetch_options_data(api_key, api_secret, base_url)
    
    if not nearest_expiry_options:
        st.error("No options data available or API request failed.")
        st.stop()
    
    # Sidebar - Select underlying asset
    available_underlyings = list(nearest_expiry_options.keys())
    selected_underlying = st.sidebar.selectbox(
        "Select Underlying Asset:",
        available_underlyings,
        index=0 if available_underlyings else None
    )
    
    if not selected_underlying:
        st.warning("No underlying assets available.")
        st.stop()
    
    # Display options chain
    st.subheader(f"Options Chain for {selected_underlying}")
    
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
            total_call_oi = chain_df['Call_OI'].sum()
            st.metric("Total Call OI", f"{total_call_oi:,.0f}")
        
        with col3:
            total_put_oi = chain_df['Put_OI'].sum()
            st.metric("Total Put OI", f"{total_put_oi:,.0f}")
        
        with col4:
            total_volume = chain_df['Call_Volume'].sum() + chain_df['Put_Volume'].sum()
            st.metric("Total Volume (24h)", f"{total_volume:,.0f}")
        
        # Display the options chain table
        st.subheader("Options Chain Data")
        
        # Format the dataframe for better display
        display_df = chain_df.copy()
        display_df = display_df.round(4)
        
        # Color code the table
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                "Strike": st.column_config.NumberColumn("Strike Price", format="%.2f"),
                "Call_Price": st.column_config.NumberColumn("Call Price", format="%.4f"),
                "Put_Price": st.column_config.NumberColumn("Put Price", format="%.4f"),
                "Call_Volume": st.column_config.NumberColumn("Call Volume", format="%.0f"),
                "Put_Volume": st.column_config.NumberColumn("Put Volume", format="%.0f"),
                "Call_OI": st.column_config.NumberColumn("Call OI", format="%.0f"),
                "Put_OI": st.column_config.NumberColumn("Put OI", format="%.0f"),
            }
        )
        
        # Create visualizations
        st.subheader("Options Analysis")
        
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
                "Avg Call Price": chain_df[chain_df['Call_Price'] > 0]['Call_Price'].mean(),
                "Max Call OI Strike": chain_df.loc[chain_df['Call_OI'].idxmax(), 'Strike'] if not chain_df.empty else 0,
                "Total Call Volume": chain_df['Call_Volume'].sum()
            }
            for key, value in call_stats.items():
                if isinstance(value, float):
                    st.write(f"- {key}: {value:.4f}")
                else:
                    st.write(f"- {key}: {value}")
        
        with col2:
            st.write("**Put Options Summary:**")
            put_stats = {
                "Active Strikes": len(chain_df[chain_df['Put_Price'] > 0]),
                "Avg Put Price": chain_df[chain_df['Put_Price'] > 0]['Put_Price'].mean(),
                "Max Put OI Strike": chain_df.loc[chain_df['Put_OI'].idxmax(), 'Strike'] if not chain_df.empty else 0,
                "Total Put Volume": chain_df['Put_Volume'].sum()
            }
            for key, value in put_stats.items():
                if isinstance(value, float):
                    st.write(f"- {key}: {value:.4f}")
                else:
                    st.write(f"- {key}: {value}")
    
    else:
        st.warning(f"No options data available for {selected_underlying}")
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>Delta Exchange Options Chain Dashboard | Data refreshes every 5 minutes</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
