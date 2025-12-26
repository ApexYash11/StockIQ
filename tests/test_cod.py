import requests

"""Smoke tests for COD endpoints.

Run while a local server is available at http://127.0.0.1:8000.
These print prepared URLs and responses for manual verification.
"""

BASE = "http://127.0.0.1:8000"

EXISTING = {"sku_id": "SKU0001", "warehouse_id": "east"}

def prep_url(path, params):
    return requests.Request('GET', BASE + path, params=params).prepare().url


print("\n1) LIST COD by sku ->", prep_url('/cod', {"sku_id": EXISTING['sku_id']}))
r = requests.get(BASE + '/cod', params={"sku_id": EXISTING['sku_id']})
print("status", r.status_code, "rows", len(r.json()))
print(r.json()[:1])


print("\n2) LIST COD by warehouse ->", prep_url('/cod', {"warehouse_id": EXISTING['warehouse_id']}))
r2 = requests.get(BASE + '/cod', params={"warehouse_id": EXISTING['warehouse_id']})
print("status", r2.status_code, "rows", len(r2.json()))


print("\n3) DECISION existing ->", prep_url('/cod/decision', EXISTING))
r3 = requests.get(BASE + '/cod/decision', params=EXISTING)
print("status", r3.status_code)
try:
    print(r3.json())
except Exception:
    print(r3.text)


NON_EXIST = {"sku_id": "NO_SKU", "warehouse_id": "east"}
print("\n4) DECISION non-existent ->", prep_url('/cod/decision', NON_EXIST))
r4 = requests.get(BASE + '/cod/decision', params=NON_EXIST)
print("status", r4.status_code, r4.text)


print("\n5) DECISION with unexpected param ->", prep_url('/cod/decision', {**EXISTING, 'extra': 'x'}))
r5 = requests.get(BASE + '/cod/decision', params={**EXISTING, 'extra': 'x'})
print("status", r5.status_code, r5.text)

print('\nCOD tests done')
