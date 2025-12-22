import json
import os
import pandas as pd
import numpy as np

# load config relative to this script so script works when run from any CWD
base_dir = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(base_dir, "..", "config", "world_config.json")
cfg_path = os.path.abspath(cfg_path)
with open(cfg_path) as f:
    cfg = json.load(f)

rows = []

for sku in cfg.get("skus", []):
    rows.append({
        "sku_id": sku["sku_id"],
        "vendor_id": f"V_{sku['sku_id'][-3:]}",
        "lead_time_days": int(np.random.randint(7, 30)),
        "MOQ": int(np.random.choice([50, 100, 200])),
        "unit_cost": float(round(np.random.uniform(200, 1200), 2))
    })

# ensure output directory exists and write CSV there
out_dir = os.path.join(base_dir, "..", "output")
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.abspath(os.path.join(out_dir, "vendors.csv"))
pd.DataFrame(rows).to_csv(out_file, index=False)
