import os
import pandas as pd
import numpy as np

# Vendors must be one-to-one with SKUs present in orders.csv (source of truth)
base_dir = os.path.dirname(os.path.abspath(__file__))
orders_path = os.path.abspath(os.path.join(base_dir, "..", "output", "orders.csv"))
out_dir = os.path.join(base_dir, "..", "output")
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.abspath(os.path.join(out_dir, "vendors.csv"))

# deterministic randomness for reproducible vendor assignments
RNG_SEED = 42
np.random.seed(RNG_SEED)

# load SKUs from orders.csv; orders.csv is authoritative for SKUs
if os.path.exists(orders_path):
    orders = pd.read_csv(orders_path, usecols=["sku_id"]) if "sku_id" in pd.read_csv(orders_path, nrows=0).columns else pd.DataFrame(columns=["sku_id"])
    skus = sorted(orders["sku_id"].dropna().unique())
else:
    # fallback: try to read from config if orders not present
    cfg_path = os.path.abspath(os.path.join(base_dir, "..", "config", "world_config.json"))
    skus = []
    if os.path.exists(cfg_path):
        import json
        with open(cfg_path) as f:
            cfg = json.load(f)
        skus = [s.get("sku_id") for s in cfg.get("skus", [])]

# Create one vendor per SKU
rows = []
for sku in skus:
    vendor_id = f"V_{str(sku)[-6:]}"  # stable vendor id derived from sku
    lead_time = int(np.random.randint(7, 31))  # inclusive upper bound fix
    moq = int(np.random.choice([50, 100, 200]))
    unit_cost = float(round(np.random.uniform(50, 1000), 2))  # realistic unit cost range
    rows.append({
        "sku_id": sku,
        "vendor_id": vendor_id,
        "lead_time_days": lead_time,
        "MOQ": moq,
        "unit_cost": unit_cost,
    })

# write vendors.csv (overwrite in-place)
vendors_df = pd.DataFrame(rows)
vendors_df.to_csv(out_file, index=False)

# Validation: exactly one vendor per unique SKU
assert len(vendors_df) == len(skus), "vendors.csv must contain exactly one row per SKU from orders.csv"
