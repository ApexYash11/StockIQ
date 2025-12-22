import os
import json
import math
import numpy as np
import pandas as pd

# Deterministic campaign augmenter for demo: boost signal-to-noise so campaigns are
# statistically detectable while preserving realism and avoiding duplicates.
# Strategy:
#  - Ensure each campaign's uplift multiplier is at least `MIN_UPLIFT` (deterministic)
#  - Concentrate injected incremental demand on the top `TOP_SKU_FRAC` of SKUs by volume
#  - For each campaign day, deterministically compute `target_count = round(current_day_count * uplift)`
#    and inject `extra = target_count - current_count` sampled orders (with replacement) from the day's
#    orders preferring top SKUs. Newly injected rows get unique deterministic `order_id`s and
#    `campaign_applied=True`.

base_dir = os.path.dirname(os.path.abspath(__file__))
orders_path = os.path.abspath(os.path.join(base_dir, "..", "output", "orders.csv"))
cfg_path = os.path.abspath(os.path.join(base_dir, "..", "config", "world_config.json"))

RNG_SEED = 42
np.random.seed(RNG_SEED)

MIN_UPLIFT = 1.8        # minimum deterministic multiplier to make campaigns detectable
TOP_SKU_FRAC = 0.30     # concentrate uplift on top 30% SKUs
MIN_MEAN_MULT = 1.15    # require mean(IN) >= mean(OUT) * MIN_MEAN_MULT

if not os.path.exists(orders_path):
    raise SystemExit("orders.csv not found in output/ — run order generator first")

orders = pd.read_csv(orders_path)

if "order_date" not in orders.columns:
    raise SystemExit("orders.csv must contain 'order_date' column with integer day offsets")

if not os.path.exists(cfg_path):
    raise SystemExit("config/world_config.json not found — cannot apply campaigns")
with open(cfg_path) as f:
    cfg = json.load(f)

campaigns = cfg.get("campaigns", [])
if not campaigns:
    print("No campaigns found in config — nothing to apply")
    raise SystemExit(0)

# Build campaign day set
campaign_days = set()
for c in campaigns:
    start = int(c.get("start_date_offset", c.get("start_day", 0)))
    dur = int(c.get("duration_days", c.get("duration", 0)))
    for d in range(start, start + dur):
        campaign_days.add(d)

# Baseline mean: use pre-existing non-campaign-applied orders when available
if "campaign_applied" in orders.columns:
    baseline_mask = (~orders["campaign_applied"]) & (~orders["order_date"].isin(campaign_days))
    baseline_days = sorted(list(set(orders.loc[baseline_mask, "order_date"].tolist())))
    if baseline_days:
        mean_baseline = orders[baseline_mask].shape[0] / max(1, len(baseline_days))
    else:
        all_days = sorted(list(set(orders["order_date"].tolist())))
        mean_baseline = orders.shape[0] / max(1, len(all_days))
else:
    all_days = sorted(list(set(orders["order_date"].tolist())))
    baseline_days = [d for d in all_days if d not in campaign_days]
    mean_baseline = orders[orders["order_date"].isin(baseline_days)].shape[0] / max(1, len(baseline_days)) if baseline_days else orders.shape[0] / max(1, len(all_days))

# Determine top SKUs to concentrate uplift
sku_counts = orders["sku_id"].value_counts()
unique_skus = sku_counts.shape[0]
top_k = max(1, int(math.ceil(unique_skus * TOP_SKU_FRAC)))
top_skus = set(sku_counts.nlargest(top_k).index.tolist())

augmented_rows = []
next_cam_id = 0

for c in campaigns:
    campaign_id = str(c.get("campaign_id", c.get("id", f"camp_{next_cam_id}")))
    next_cam_id += 1
    start = int(c.get("start_date_offset", c.get("start_day", 0)))
    dur = int(c.get("duration_days", c.get("duration", 0)))
    cfg_uplift = float(c.get("uplift_multiplier", c.get("uplift", 1.0)))
    uplift = max(cfg_uplift, MIN_UPLIFT)  # deterministic minimum uplift

    for day in range(start, start + dur):
        day_orders = orders[orders["order_date"] == day]
        current_n = len(day_orders)
        # If no orders that day, use baseline mean as a target anchor
        if current_n == 0:
            target_n = int(round(mean_baseline * uplift))
        else:
            target_n = int(round(current_n * uplift))

        extra = max(0, target_n - current_n)
        if extra == 0:
            continue

        # Prefer sampling rows for top SKUs on that day; fallback to all day orders; if still empty, sample globally
        candidates = day_orders[day_orders["sku_id"].isin(top_skus)]
        if candidates.empty:
            candidates = day_orders
        if candidates.empty:
            candidates = orders[orders["sku_id"].isin(top_skus)]
        if candidates.empty:
            candidates = orders

        # deterministic sampling with replacement
        sampled = candidates.sample(n=extra, replace=True, random_state=RNG_SEED + day + hash(campaign_id) % 997).copy()

        # Build new deterministic order_ids and mark campaign_applied=True
        start_idx = 0
        new_rows = []
        for i, (_, srow) in enumerate(sampled.iterrows()):
            # Create a collision-resistant deterministic id; prefix ensures uniqueness vs prior IDs
            new_id = f"CAM_{campaign_id}_{day}_{i}"
            row = srow.copy()
            row["order_id"] = new_id
            # Ensure campaign flag is True only for injected orders
            row["campaign_applied"] = True
            # Keep order_quantity if present; otherwise set to 1
            if "order_quantity" not in row or pd.isna(row["order_quantity"]):
                row["order_quantity"] = 1
            new_rows.append(row)

        if new_rows:
            augmented_rows.extend(new_rows)

if augmented_rows:
    aug_df = pd.DataFrame(augmented_rows)
    # Ensure no order_id collision with existing ids; if any collision, suffix with incremental counter
    existing_ids = set(orders["order_id"].astype(str).tolist())
    def ensure_unique(oid, used):
        if oid not in used:
            used.add(oid)
            return oid
        i = 1
        while f"{oid}_{i}" in used:
            i += 1
        new = f"{oid}_{i}"
        used.add(new)
        return new

    used_ids = set(existing_ids)
    aug_df["order_id"] = aug_df["order_id"].astype(str).apply(lambda x: ensure_unique(x, used_ids))

    orders_out = pd.concat([orders, aug_df], ignore_index=True)
    orders_out = orders_out.sort_values(by=["order_date"]).reset_index(drop=True)
    orders_out.to_csv(orders_path, index=False)
    added = len(aug_df)
    print(f"Appended {added} campaign-driven orders (deterministic) and wrote {orders_path}")

    # Recompute stats and validate uplift is detectable
    campaign_days_list = sorted(list(campaign_days))
    # compute mean per day IN campaign and OUT (exclude prior campaign_applied where possible)
    df = orders_out
    if "campaign_applied" in df.columns:
        out_mask = (~df["order_date"].isin(campaign_days_list))
        in_mask = df["order_date"].isin(campaign_days_list)
        mean_in = df[in_mask].shape[0] / max(1, len(campaign_days_list))
        mean_out = df[out_mask].shape[0] / max(1, len(set(df.loc[out_mask, "order_date"].tolist())))
    else:
        mean_in = df[df["order_date"].isin(campaign_days_list)].shape[0] / max(1, len(campaign_days_list))
        all_days = sorted(list(set(df["order_date"].tolist())))
        baseline_days = [d for d in all_days if d not in campaign_days_list]
        mean_out = df[df["order_date"].isin(baseline_days)].shape[0] / max(1, len(baseline_days)) if baseline_days else mean_in

    print(f"Mean orders/day DURING campaigns: {mean_in:.2f}")
    print(f"Mean orders/day OUTSIDE campaigns: {mean_out:.2f}")
    assert mean_in > mean_out * MIN_MEAN_MULT, f"Uplift not detectable: mean_in={mean_in:.2f} mean_out={mean_out:.2f}"

else:
    print("No augmented rows were generated — no changes applied")

# COD RTO validation preserved
if "payment_type" in orders.columns and "delivery_status" in orders.columns:
    cod = orders[orders["payment_type"] == "COD"]
    prepaid = orders[orders["payment_type"] != "COD"]
    if len(cod) and len(prepaid):
        rto_cod = (cod["delivery_status"] == "RTO").mean()
        rto_pre = (prepaid["delivery_status"] == "RTO").mean()
        assert rto_cod >= rto_pre, "COD RTO rate must be >= prepaid RTO rate"

print("Campaign application complete")
