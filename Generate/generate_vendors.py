import pandas as pd
import numpy as np
import os

np.random.seed(42)
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

orders = pd.read_csv(f"{OUTPUT_DIR}/orders.csv")
skus = orders["sku_id"].unique()

rows = []

for sku in skus:
    rows.append({
        "sku_id": sku,
        "vendor_id": f"V_{sku[-3:]}",
        "lead_time_days": np.random.choice([7, 14, 21, 28]),
        "MOQ": np.random.choice([50, 100, 200, 500]),
        "vendor_reliability": round(np.random.uniform(0.85, 0.98), 2),
    })

pd.DataFrame(rows).to_csv(f"{OUTPUT_DIR}/vendors.csv", index=False)
