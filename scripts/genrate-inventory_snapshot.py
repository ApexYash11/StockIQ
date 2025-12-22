import pandas as pd
import random

random.seed(42)

warehouses = [
    {"warehouse_id": "WH-DEL-C", "warehouse_type": "Central", "region": "Delhi NCR"},
    {"warehouse_id": "WH-MUM-R", "warehouse_type": "Regional", "region": "Mumbai"},
    {"warehouse_id": "WH-BLR-R", "warehouse_type": "Regional", "region": "Bangalore"},
]

skus = [
    "TS-BLK-S","TS-BLK-M","TS-BLK-L","TS-WHT-M",
    "HD-BLK-M","HD-GRY-L","JK-DNM-M","CP-BLK"
]

rows = []

for wh in warehouses:
    for sku in skus:
        if wh["warehouse_type"] == "Central":
            available = random.randint(150, 400)
        else:
            available = random.randint(20, 120)

        reserved = random.randint(0, int(available * 0.3))

        rows.append({
            "warehouse_id": wh["warehouse_id"],
            "warehouse_type": wh["warehouse_type"],
            "region": wh["region"],
            "sku_id": sku,
            "available_stock": available,
            "reserved_stock": reserved
        })

df = pd.DataFrame(rows)
df.to_csv("Data/inventory_snapshot.csv", index=False)

print(f"Inventory snapshot generated: {len(df)} rows")
