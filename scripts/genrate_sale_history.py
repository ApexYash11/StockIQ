import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

np.random.seed(42)

skus = [
    "TS-BLK-S","TS-BLK-M","TS-BLK-L","TS-WHT-M",
    "HD-BLK-M","HD-GRY-L","JK-DNM-M","CP-BLK"
]

regions = ["Delhi NCR", "Mumbai", "Bangalore"]
channels = ["Website", "Marketplace"]

start_date = datetime(2024, 8, 1)
days = 90

rows = []

for day in range(days):
    date = start_date + timedelta(days=day)
    is_festival = 1 if 35 <= day <= 40 else 0  # festival spike

    for sku in skus:
        for region in regions:
            base_demand = random.randint(1, 5)

            if "Hoodie" in sku or "JK" in sku:
                base_demand += random.randint(0, 2)

            demand = base_demand + (random.randint(3, 6) if is_festival else 0)

            for _ in range(demand):
                rows.append({
                    "order_date": date.date(),
                    "sku_id": sku,
                    "region": region,
                    "channel": random.choice(channels),
                    "quantity": random.randint(1, 2),
                    "payment_type": "COD" if random.random() < 0.6 else "Prepaid"
                })

df = pd.DataFrame(rows)
df.to_csv("Data/sales_history.csv", index=False)

print(f"Sales history generated: {len(df)} rows")
