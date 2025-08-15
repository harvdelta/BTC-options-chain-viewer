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
    page_title="Delta Exchange Debug",
    page_icon="🔍",
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
        
        # Debug information
        st.write("**Debug Info:**")
        st.write(f"- URL: {url}")
        st.write(f"- Method: {method}")
        st.write(f"- Headers: {headers}")
        st.write(f"- Timestamp: {timestamp}")
        st.write(f"- Payload: {payload}")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            
            st.write(f"- Response Status: {response.status_code}")
            st.write(f"- Response Headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                st.error(f"API Error {response.status_code}: {response.text}")
                return None
            
            response_data = response.json()
            st.write(f"- Response Keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            st.error(f"JSON decode error: {str(e)}")
            st.write(f"Raw response: {response.text}")
            return None
    
    def get_products(self):
        """Get all available products"""
        return self._make_request("GET", "/v2/products")
    
    def get_public_products(self):
        """Try public endpoint without authentication"""
        url = f"{self.base_url}/v2/products"
        try:
            response = requests.get(url, timeout=30)
            st.write(f"Public API Status: {response.status_code}")
            if response.status_code == 200:
                return response.json()
            else:
                st.write(f"Public API Error: {response.text}")
                return None
        except Exception as e:
            st.error(f"Public API failed: {str(e)}")
            return None
    
    def test_connection(self):
        """Test basic connectivity"""
        try:
            response = requests.get(self.base_url, timeout=10)
            st.write(f"Base URL connectivity test: {response.status_code}")
            return True
        except Exception as e:
            st.error(f"Base URL not reachable: {str(e)}")
            return False

def main():
    st.title("🔍 Delta Exchange API Debug Tool")
    st.markdown("---")
    
    # Get API credentials
    try:
        # First try from secrets
        api_key = st.secrets["delta_exchange"]["api_key"]
        api_secret = st.secrets["delta_exchange"]["api_secret"]
        base_url = st.secrets["delta_exchange"].get("base_url", "https://api.india.delta.exchange")
    except:
        # Fallback to direct input for debugging
        st.warning("Secrets not found, using manual input for debugging")
        api_key = "LkxpWQGihtxtBUJfCGx1uSTpvyIqQl"
        api_secret = "aG9aklujDrFK8nPZMyo6UJr6wsAyTDf3tEjM3bz5s1QtN3Cm2Q0OYqRd3cGl"
        base_url = "https://api.india.delta.exchange"
    
    st.write(f"**Configuration:**")
    st.write(f"- API Key: {api_key[:10]}...")
    st.write(f"- Base URL: {base_url}")
    
    api = DeltaExchangeAPI(api_key, api_secret, base_url)
    
    # Test different approaches
    st.subheader("1. Connection Test")
    api.test_connection()
    
    st.subheader("2. Public API Test (No Auth)")
    public_result = api.get_public_products()
    if public_result:
        st.success("✅ Public API works!")
        if isinstance(public_result, dict) and 'result' in public_result:
            products = public_result['result']
            st.write(f"Found {len(products)} products")
            
            # Show first few products
            st.write("**Sample Products:**")
            for i, product in enumerate(products[:3]):
                st.json(product)
            
            # Count product types
            product_types = {}
            for product in products:
                ptype = product.get('product_type', 'unknown')
                product_types[ptype] = product_types.get(ptype, 0) + 1
            
            st.write("**Product Types:**")
            for ptype, count in product_types.items():
                st.write(f"- {ptype}: {count}")
    else:
        st.error("❌ Public API failed")
    
    st.subheader("3. Authenticated API Test")
    auth_result = api.get_products()
    if auth_result:
        st.success("✅ Authenticated API works!")
    else:
        st.error("❌ Authenticated API failed")
    
    # Manual test section
    st.subheader("4. Manual Endpoint Test")
    test_endpoint = st.text_input("Enter endpoint to test:", "/v2/products")
    if st.button("Test Endpoint"):
        result = api._make_request("GET", test_endpoint)
        if result:
            st.json(result)
    
    # Alternative base URLs to try
    st.subheader("5. Alternative Base URLs")
    alternative_urls = [
        "https://api.delta.exchange",
        "https://api.india.delta.exchange", 
        "https://api-v2.delta.exchange",
        "https://testnet-api.delta.exchange"
    ]
    
    for alt_url in alternative_urls:
        if st.button(f"Test {alt_url}"):
            try:
                test_api = DeltaExchangeAPI(api_key, api_secret, alt_url)
                result = test_api.get_public_products()
                if result:
                    st.success(f"✅ {alt_url} works!")
                    st.json(result)
                else:
                    st.error(f"❌ {alt_url} failed")
            except Exception as e:
                st.error(f"❌ {alt_url} error: {str(e)}")

if __name__ == "__main__":
    main()
