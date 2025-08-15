# BTC Options Chain Viewer

A simple Streamlit app to display the nearest expiry BTC options chain from Delta Exchange, showing only the Mark Price for Calls and Puts.

## Features
- Fetches live options chain data from Delta Exchange.
- Displays Calls and Puts side-by-side, Strike in the middle.
- Omits Bid, Ask, and IV — only shows Mark Price.

## How to Run Locally
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
