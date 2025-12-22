import os
import json
import pandas as pd
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))
orders_path = os.path.abspath(os.path.join(base_dir, "..", "output", "orders.csv"))
cfg_path = os.path.abspath(os.path.join(base_dir, "..", "config", "world_config.json"))

events = []

# load orders if available
if os.path.exists(orders_path):
    orders = pd.read_csv(orders_path)
else:
    orders = pd.DataFrame()

# determine warehouses
if not orders.empty and "warehouse_fulfilled" in orders.columns:
    warehouses = list(orders["warehouse_fulfilled"].dropna().unique())
elif os.path.exists(cfg_path):
    with open(cfg_path) as f:
        cfg = json.load(f)
    # use warehouses from config if present, else derive from regions
    if cfg.get("warehouses"):
        warehouses = [w.get("id") if isinstance(w, dict) else str(w) for w in cfg["warehouses"]]
    else:
        warehouses = [f"WH_{r.get('name')}" for r in cfg.get("regions", [])] or ["WH_1"]
else:
    warehouses = ["WH_1"]

# determine skus
if not orders.empty and "sku_id" in orders.columns:
    skus = list(orders["sku_id"].unique())
elif os.path.exists(cfg_path):
    with open(cfg_path) as f:
        cfg = json.load(f)
    skus = [s.get("sku_id") if isinstance(s, dict) else str(s) for s in cfg.get("skus", [])] or [f"SKU{i:04d}" for i in range(1, 6)]
else:
    skus = [f"SKU{i:04d}" for i in range(1, 6)]

# Initial stock events
for wh in warehouses:
    for sku in skus:
        events.append({
            "timestamp": 0,
            "warehouse": wh,
            "sku_id": sku,
            "event": "INITIAL_STOCK",
            "quantity": int(np.random.randint(500, 2000)),
        })

# Depletion events from orders (if any)
if not orders.empty:
    for _, row in orders.iterrows():
        # timestamp fallback
        ts = row.get("order_date") if "order_date" in row.index else 0
        # warehouse: prefer fulfilled column, then warehouse, fallback to first warehouse
        if "warehouse_fulfilled" in orders.columns:
            wh = row["warehouse_fulfilled"] if pd.notna(row["warehouse_fulfilled"]) else (row.get("warehouse") if "warehouse" in row.index else warehouses[0])
        else:
            wh = row.get("warehouse") if "warehouse" in row.index else warehouses[0]
        sku_id = row["sku_id"] if "sku_id" in row.index else (row.get("SKU") if "SKU" in row.index else skus[0])
        qty = -abs(int(row.get("quantity", 1))) if "quantity" in row.index else -1
        events.append({
            "timestamp": ts,
            "warehouse": wh,
            "sku_id": sku_id,
            "event": "OUTBOUND",
            "quantity": qty,
        })

# ensure output directory exists and write
out_dir = os.path.abspath(os.path.join(base_dir, "..", "output"))
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "inventory_events.csv")
inventory_df = pd.DataFrame(events)
inventory_df.to_csv(out_file, index=False)
print(f"Wrote {len(events)} inventory events to {out_file}")
