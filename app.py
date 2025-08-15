import requests

symbol = "P-BTC-116400-160825"  # example
url = f"https://api.delta.exchange/v2/tickers/{symbol}"

r = requests.get(url)
print("Status Code:", r.status_code)

try:
    data = r.json()
except Exception as e:
    print("Error parsing JSON:", e)
    data = {}

print("Full API response:", data)

result = data.get("result", {})
bid = result.get("best_bid_price")
ask = result.get("best_ask_price")

print(f"Best Bid: {bid}")
print(f"Best Ask: {ask}")
