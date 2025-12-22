import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

skus = [
    "TS-BLK-S","TS-BLK-M","TS-BLK-L","TS-WHT-M",
    "HD-BLK-M","HD-GRY-L","JK-DNM-M","CP-BLK"
]

regions = ["Delhi NCR", "Mumbai", "Bangalore"]

orders = []
base_date = datetime(2024, 11, 10)

for i in range(1, 101):  # 100 orders
    orders.append({
        "order_id": f"ORD-{1000+i}",
        "order_date": (base_date + timedelta(minutes=i*5)).strftime("%Y-%m-%d %H:%M:%S"),
        "sku_id": random.choice(skus),
        "quantity": random.randint(1, 2),
        "customer_region": random.choice(regions),
        "payment_type": "COD" if random.random() < 0.6 else "Prepaid"
    })

df = pd.DataFrame(orders)
df.to_csv("Data/incoming_orders.csv", index=False)

print("Incoming orders generated: 100 orders")
