import json
import os
import pandas as pd

# load config relative to this script so script works when run from any CWD
base_dir = os.path.dirname(os.path.abspath(__file__))
cfg_path = os.path.join(base_dir, "..", "config", "world_config.json")
cfg_path = os.path.abspath(cfg_path)
with open(cfg_path) as f:
    cfg = json.load(f)

campaigns = []

for c in cfg["campaigns"]:
    campaigns.append({
        "campaign_id": c["name"],
        "start_day": c["start_date_offset"],
        "duration_days": c["duration_days"],
        "uplift": c["uplift_multiplier"],
        "categories": ",".join(c["affected_categories"])
    })

df = pd.DataFrame(campaigns)

# ensure output directory exists and write CSV there
out_dir = os.path.join(base_dir, "..", "output")
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.abspath(os.path.join(out_dir, "campaigns.csv"))
df.to_csv(out_file, index=False)
