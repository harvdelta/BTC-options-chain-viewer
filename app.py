import requests

symbol = "P-BTC-116400-160825"  # example from your screenshot
url = f"https://api.delta.exchange/v2/tickers/{symbol}"

r = requests.get(url)
data = r.json()

print("Full API response:", data)

if "result" in data:
    bid = data["result"]["best_bid_price"]
    ask = data["result"]["best_ask_price"]
    print(f"Best Bid: {bid}")
    print(f"Best Ask: {ask}")
