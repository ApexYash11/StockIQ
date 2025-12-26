import requests

# Use an existing key from artifacts/weekly_forecast_future_all_skus.csv
params = {"sku_id": "SKU0001", "week": "2024-12-23"}

list_url = "http://127.0.0.1:8000/forecast"
decision_url = "http://127.0.0.1:8000/forecast/decision"

print("LIST ->", requests.Request('GET', list_url, params=params).prepare().url)
r = requests.get(list_url, params=params)
print(r.status_code, r.json())

print("DECISION ->", requests.Request('GET', decision_url, params=params).prepare().url)
r2 = requests.get(decision_url, params=params)
try:
	print(r2.status_code, r2.json())
except Exception:
	print(r2.status_code, r2.text)