import json
import os
import numpy as np
import pandas as pd
from tqdm import tqdm

# constants
DAYS = 365 * 2
ORDERS_PER_DAY = 3000  # scale this

# load config relative to this script so script works when run from any CWD
base_dir = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(base_dir, "..", "config", "world_config.json")
with open(os.path.abspath(cfg_path)) as f:
    cfg = json.load(f)

orders = []

# fallback defaults
default_sku = {"sku_id": "UNKNOWN", "base_daily_demand": 1, "demand_volatility": 1}
default_region = {"name": "unknown", "COD_rate": 0.0, "RTO_rate_for_COD": 0.0, "RTO_rate_for_prepaid": 0.0, "avg_delivery_days": 3}

skus = cfg.get("skus", [])
regions = cfg.get("regions", [])

for day in tqdm(range(DAYS)):
    for _ in range(ORDERS_PER_DAY):
        sku = np.random.choice(skus) if skus else default_sku
        region = np.random.choice(regions) if regions else default_region

        base = sku.get("base_daily_demand", 1)
        volatility = sku.get("demand_volatility", 1)
        demand = max(1, int(np.random.normal(base, volatility)))

        is_cod = np.random.rand() < region.get("COD_rate", 0.0)
        rto_prob = region.get("RTO_rate_for_COD") if is_cod else region.get("RTO_rate_for_prepaid")
        rto_prob = rto_prob if rto_prob is not None else 0.0

        rto = np.random.rand() < rto_prob

        orders.append({
            "order_date": day,
            "sku_id": sku.get("sku_id", "UNKNOWN"),
            "region": region.get("name", "unknown"),
            "payment_type": "COD" if is_cod else "PREPAID",
            "delivery_days": int(np.random.normal(region.get("avg_delivery_days", 3), 1)),
            "delivery_status": "RTO" if rto else "DELIVERED"
        })

# ensure output dir exists and write CSV
out_dir = os.path.abspath(os.path.join(base_dir, "..", "output"))
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "orders.csv")
df = pd.DataFrame(orders)
df.to_csv(out_file, index=False)
