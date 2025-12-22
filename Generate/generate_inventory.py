import os
import json
import pandas as pd
import numpy as np
from collections import defaultdict

# Generate inventory events (INITIAL_STOCK, OUTBOUND, REPLENISHMENT_INBOUND)
# - Uses orders.csv as the source of truth for SKUs and timestamps
# - Uses vendors.csv for lead times and MOQs
# - Schedules replenishments when running stock < threshold
# - Ensures events are written in timestamp order and that inventory is not permanently negative

base_dir = os.path.dirname(os.path.abspath(__file__))
orders_path = os.path.abspath(os.path.join(base_dir, "..", "output", "orders.csv"))
vendors_path = os.path.abspath(os.path.join(base_dir, "..", "output", "vendors.csv"))
cfg_path = os.path.abspath(os.path.join(base_dir, "..", "config", "world_config.json"))

# Deterministic seed for reproducible initial stock and scheduling
RNG_SEED = 42
np.random.seed(RNG_SEED)

events = []

# Load orders (source of truth) if present
if os.path.exists(orders_path):
    orders = pd.read_csv(orders_path)
else:
    orders = pd.DataFrame()

# Build vendor lookup: SKU -> {lead_time, MOQ}
vendor_lookup = {}
if os.path.exists(vendors_path):
    vdf = pd.read_csv(vendors_path)
    for _, r in vdf.iterrows():
        vendor_lookup[r["sku_id"]] = {"lead_time": int(r.get("lead_time_days", 14)), "MOQ": int(r.get("MOQ", 100))}

# Determine warehouses and skus
if not orders.empty:
    if "warehouse_fulfilled" in orders.columns:
        warehouses = sorted(orders["warehouse_fulfilled"].dropna().unique())
    elif "warehouse" in orders.columns:
        warehouses = sorted(orders["warehouse"].dropna().unique())
    else:
        warehouses = ["WH_1"]
    skus = sorted(orders["sku_id"].dropna().unique()) if "sku_id" in orders.columns else []
else:
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
        warehouses = [w.get("id") for w in cfg.get("warehouses", [])] or [f"WH_{r.get('name')}" for r in cfg.get("regions", [])] or ["WH_1"]
        skus = [s.get("sku_id") for s in cfg.get("skus", [])] or [f"SKU{i:04d}" for i in range(1, 6)]
    else:
        warehouses = ["WH_1"]
        skus = [f"SKU{i:04d}" for i in range(1, 6)]

        # INITIAL_STOCK events at timestamp 0 (preserve)
        initial_stock = {}
        for wh in warehouses:
            for sku in skus:
                # deterministic-ish initial stock per warehouse/sku
                seed_val = abs(hash(f"{wh}|{sku}")) % (2 ** 32)
                rng = np.random.RandomState((RNG_SEED + seed_val) % (2 ** 32))
                qty = int(rng.randint(500, 2000))
                initial_stock[(wh, sku)] = qty
                events.append({
                    "timestamp": 0,
                    "warehouse": wh,
                    "sku_id": sku,
                    "event": "INITIAL_STOCK",
                    "quantity": qty,
                })

        # Process orders chronologically and schedule replenishments when needed
        threshold = 200  # reorder threshold

        # current stock state includes initial and applied replenishments
        current_stock = dict(initial_stock)
        # scheduled inbounds: (wh,sku) -> list of (arrival_ts, qty)
        scheduled = defaultdict(list)

        # Helper to schedule replenishment
        def schedule_replenishment(wh, sku, now_ts):
            v = vendor_lookup.get(sku, {"lead_time": 14, "MOQ": 100})
            arrival = int(now_ts) + int(v["lead_time"])
            qty = int(v["MOQ"])
            # record scheduled and create event row (REPLENISHMENT_INBOUND)
            scheduled[(wh, sku)].append((arrival, qty))
            events.append({
                "timestamp": arrival,
                "warehouse": wh,
                "sku_id": sku,
                "event": "REPLENISHMENT_INBOUND",
                "quantity": qty,
            })

        # sort orders by order_date to simulate time
        if not orders.empty:
            if "order_date" in orders.columns:
                orders_sorted = orders.sort_values(by="order_date")
            else:
                orders_sorted = orders

            # iterate orders and update stock; process scheduled arrivals when their time comes
            last_ts = 0
            for _, row in orders_sorted.iterrows():
                ts = int(row.get("order_date", 0))
                # materialize scheduled arrivals up to ts
                if ts != last_ts:
                    # process arrivals whose arrival <= ts
                    for key, arrs in list(scheduled.items()):
                        arrivals_now = [a for a in arrs if a[0] <= ts]
                        if arrivals_now:
                            for a_ts, a_qty in arrivals_now:
                                current_stock[key] = current_stock.get(key, 0) + int(a_qty)
                            # remove processed arrivals
                            scheduled[key] = [a for a in arrs if a[0] > ts]
                    last_ts = ts

                # determine warehouse for this order
                if "warehouse_fulfilled" in orders.columns:
                    wh = row.get("warehouse_fulfilled") if pd.notna(row.get("warehouse_fulfilled")) else (row.get("warehouse") if "warehouse" in orders.columns else warehouses[0])
                else:
                    wh = row.get("warehouse") if "warehouse" in orders.columns else warehouses[0]
                sku = row.get("sku_id") if "sku_id" in row.index else skus[0]

                key = (wh, sku)
                # ensure key in current_stock
                if key not in current_stock:
                    current_stock[key] = int(np.random.randint(500, 2000))

                # apply outbound (preserve OUTBOUND events from orders)
                qty = -1
                events.append({
                    "timestamp": ts,
                    "warehouse": wh,
                    "sku_id": sku,
                    "event": "OUTBOUND",
                    "quantity": qty,
                })
                current_stock[key] += qty

                # if stock below threshold after this outbound, schedule replenishment
                if current_stock[key] < threshold:
                    schedule_replenishment(wh, sku, ts)

            # after processing all orders, process any remaining scheduled arrivals to compute final stock
            for key, arrs in scheduled.items():
                for a_ts, a_qty in arrs:
                    current_stock[key] = current_stock.get(key, 0) + int(a_qty)

            # ensure no permanent negatives: if final stock negative, schedule an extra replenishment now (arrival = last_ts + lead_time)
            for key, stk in list(current_stock.items()):
                if stk < 0:
                    wh, sku = key
                    v = vendor_lookup.get(sku, {"lead_time": 14, "MOQ": 100})
                    arrival = last_ts + int(v["lead_time"])
                    qty = int(v["MOQ"])
                    events.append({
                        "timestamp": arrival,
                        "warehouse": wh,
                        "sku_id": sku,
                        "event": "REPLENISHMENT_INBOUND",
                        "quantity": qty,
                    })
                    current_stock[key] += qty

            # Final check: inventory should not be permanently negative after applying scheduled replenishments
            negative_final = {k: v for k, v in current_stock.items() if v < 0}
            assert not negative_final, f"Final inventory negative for some (warehouse,sku): {list(negative_final.items())}"

        # Write out events sorted by timestamp to maintain event-sourced ordering
        inventory_df = pd.DataFrame(events)
        if not inventory_df.empty:
            inventory_df = inventory_df.sort_values(by=["timestamp", "warehouse", "sku_id"]).reset_index(drop=True)

        out_dir = os.path.abspath(os.path.join(base_dir, "..", "output"))
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, "inventory_events.csv")
        inventory_df.to_csv(out_file, index=False)
        print(f"Wrote {len(inventory_df)} inventory events to {out_file}")

        # Validation assertions
        ev_types = set(inventory_df["event"]) if not inventory_df.empty else set()
        assert {"INITIAL_STOCK", "OUTBOUND", "REPLENISHMENT_INBOUND"}.issubset(ev_types), "inventory_events must contain INITIAL_STOCK, OUTBOUND and REPLENISHMENT_INBOUND"
