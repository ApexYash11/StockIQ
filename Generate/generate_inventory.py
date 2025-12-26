import pandas as pd
import numpy as np
import os

np.random.seed(42)
OUTPUT_DIR = "output"

orders = pd.read_csv(f"{OUTPUT_DIR}/orders.csv")

weekly = (
    orders.groupby(["warehouse_id", "sku_id", "order_week"])
    .size()
    .reset_index(name="weekly_demand")
)

rows = []

for (wh, sku), df in weekly.groupby(["warehouse_id", "sku_id"]):
    stock = np.random.randint(200, 600)

    for _, r in df.iterrows():
        demand = r["weekly_demand"]
        stock -= demand

        if stock < 100:
            reorder_qty = np.random.choice([200, 300, 500])
            stock += reorder_qty
        else:
            reorder_qty = 0

        rows.append({
            "warehouse_id": wh,
            "sku_id": sku,
            "order_week": r["order_week"],
            "weekly_demand": demand,
            "ending_stock": stock,
            "reorder_qty": reorder_qty,
        })

pd.DataFrame(rows).to_csv(f"{OUTPUT_DIR}/inventory_events.csv", index=False)
