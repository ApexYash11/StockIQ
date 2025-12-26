import requests

"""Smoke tests for Reorder endpoints.

Run while a local server is available at http://127.0.0.1:8000.
These print prepared URLs and responses for manual verification.
"""

BASE = "http://127.0.0.1:8000"

# Choose an existing key from artifacts/reorder_recommendations.csv
EXISTING = {"sku_id": "SKU0024", "warehouse_id": "north"}

def prep_url(path, params):
    return requests.Request('GET', BASE + path, params=params).prepare().url


print("\n1) LIST reorder by sku ->", prep_url('/reorder', {"sku_id": EXISTING['sku_id']}))
r = requests.get(BASE + '/reorder', params={"sku_id": EXISTING['sku_id']})
print("status", r.status_code, "rows", len(r.json()))
print(r.json()[:1])


print("\n2) LIST reorder by warehouse ->", prep_url('/reorder', {"warehouse_id": EXISTING['warehouse_id']}))
r2 = requests.get(BASE + '/reorder', params={"warehouse_id": EXISTING['warehouse_id']})
print("status", r2.status_code)
try:
    rows_r2 = r2.json()
    print("rows", len(rows_r2))
except Exception as e:
    print("failed to parse JSON:", type(e).__name__, e)
    print("response text (first 1000 chars):")
    print(r2.text[:1000])


print("\n3) LIST reorder by sku+warehouse (trim whitespace) ->", prep_url('/reorder', {"sku_id": f" {EXISTING['sku_id']} ", "warehouse_id": f" {EXISTING['warehouse_id']} "}))
r3 = requests.get(BASE + '/reorder', params={"sku_id": f" {EXISTING['sku_id']} ", "warehouse_id": f" {EXISTING['warehouse_id']} "})
print("status", r3.status_code, "rows", len(r3.json()))


print('\nReorder tests done')
