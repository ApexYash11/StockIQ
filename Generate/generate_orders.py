import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

np.random.seed(42)

# ---------------- CONFIG ----------------
START_DATE = datetime(2023, 1, 1)
NUM_WEEKS = 104
SKUS = [f"SKU{i:04d}" for i in range(1, 51)]
WAREHOUSES = ["east", "west", "north", "south"]

BASE_DEMAND = 200
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# SKU lifecycle params
sku_params = {
    sku: {
        "launch_week": np.random.randint(0, 40),
        "peak_week": np.random.randint(40, 80),
        "decay_rate": np.random.uniform(0.005, 0.02),
        "volatility": np.random.uniform(0.1, 0.25),
    }
    for sku in SKUS
}

rows = []

for week in range(NUM_WEEKS):
    week_start = START_DATE + timedelta(weeks=week)

    # weekly seasonality (simple + interpretable)
    seasonality = 1.0 + 0.2 * np.sin(2 * np.pi * week / 52)

    for sku in SKUS:
        p = sku_params[sku]

        if week < p["launch_week"]:
            continue

        if week <= p["peak_week"]:
            lifecycle_multiplier = (week - p["launch_week"] + 1) / (
                p["peak_week"] - p["launch_week"] + 1
            )
        else:
            lifecycle_multiplier = np.exp(
                -p["decay_rate"] * (week - p["peak_week"])
            )

        mean_demand = BASE_DEMAND * lifecycle_multiplier * seasonality
        noise = np.random.normal(0, p["volatility"] * mean_demand)
        weekly_demand = max(0, int(mean_demand + noise))

        for _ in range(weekly_demand):
            rows.append({
                "order_date": week_start.date(),
                "order_week": week_start.strftime("%Y-%W"),
                "sku_id": sku,
                "warehouse_id": np.random.choice(WAREHOUSES),
                "payment_type": np.random.choice(["COD", "PREPAID"], p=[0.45, 0.55]),
                "delivery_status": np.random.choice(
                    ["DELIVERED", "RTO"], p=[0.75, 0.25]
                ),
            })

pd.DataFrame(rows).to_csv(f"{OUTPUT_DIR}/orders.csv", index=False)
