import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

np.random.seed(42)
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_DATE = datetime(2023, 1, 1)

rows = []

for i in range(6):
    start_week = np.random.randint(10, 80)
    duration = np.random.randint(2, 6)

    rows.append({
        "campaign_id": f"CAMP_{i}",
        "start_date": (START_DATE + timedelta(weeks=start_week)).date(),
        "end_date": (START_DATE + timedelta(weeks=start_week + duration)).date(),
        "uplift_multiplier": round(np.random.uniform(1.2, 1.8), 2),
    })

pd.DataFrame(rows).to_csv(f"{OUTPUT_DIR}/campaigns.csv", index=False)
