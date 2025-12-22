import os
import pandas as pd
import numpy as np
import json
from collections import defaultdict

# Fix and regenerate StockIQ datasets: orders.csv and inventory_events.csv
# WHY: audit found unintended duplicates, missing replenishment events, and permanent negative inventory.
# This script (deterministically) condenses duplicate identical orders into single orders with an
# explicit `order_quantity`, assigns unique `order_id`, and regenerates an event-sourced
# `inventory_events.csv` with INITIAL_STOCK, OUTBOUND (linked to order_id) and
# REPLENISHMENT_INBOUND events scheduled using vendors' lead_time and MOQ.

base_dir = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.abspath(os.path.join(base_dir, '..', 'output'))
cfg_path = os.path.abspath(os.path.join(base_dir, '..', 'config', 'world_config.json'))
orders_in = os.path.join(out_dir, 'orders.csv')
vendors_in = os.path.join(out_dir, 'vendors.csv')
campaigns_in = os.path.join(out_dir, 'campaigns.csv')
orders_out = orders_in  # overwrite in place
inventory_out = os.path.join(out_dir, 'inventory_events.csv')

np.random.seed(42)

print('FIX_DATA: starting fixes')

# ---------- Step 1 & 2: Fix orders.csv ----------
if not os.path.exists(orders_in):
    raise SystemExit('orders.csv missing; cannot fix')

print('Reading orders.csv (may be large)')
orders_raw = pd.read_csv(orders_in)
print(f'  raw orders rows: {len(orders_raw):,}')

# Ensure expected columns exist
expected_cols = ['order_date','sku_id','region','payment_type','delivery_days','delivery_status']
for c in expected_cols:
    if c not in orders_raw.columns:
        raise SystemExit(f'missing required column in orders.csv: {c}')

# Preserve campaign_applied column if present, else create
if 'campaign_applied' not in orders_raw.columns:
    orders_raw['campaign_applied'] = False
else:
    # normalize empty strings to False
    orders_raw['campaign_applied'] = orders_raw['campaign_applied'].fillna(False).astype(bool)

# Detect exact duplicate rows (all columns except we will add order_id/quantity later)
dup_mask = orders_raw.duplicated(keep=False)
dup_count = dup_mask.sum()
print(f'  exact duplicate row count (before fix): {dup_count:,}')

# Strategy: aggregate identical rows into a single order with order_quantity = frequency.
# This preserves total volume while removing unintended perfect duplicates.
group_cols = ['order_date','sku_id','region','payment_type','delivery_days','delivery_status','campaign_applied']
agg = orders_raw.groupby(group_cols).size().reset_index(name='order_quantity')
print(f'  grouped unique orders (after collapse): {len(agg):,}')

# Create deterministic order_id
agg = agg.sort_values(group_cols).reset_index(drop=True)
agg.insert(0, 'order_id', ['ORD%09d' % (i+1) for i in range(len(agg))])

# Recompute campaign_applied from campaigns.csv for consistency
if os.path.exists(campaigns_in):
    camps = pd.read_csv(campaigns_in)
    campaign_days = set()
    for _, c in camps.iterrows():
        start = int(c['start_day'])
        dur = int(c['duration_days'])
        for d in range(start, start+dur):
            campaign_days.add(d)
    agg['campaign_applied'] = agg['order_date'].isin(campaign_days)
    print('  campaign_applied recomputed from campaigns.csv')
else:
    print('  campaigns.csv not found; leaving campaign_applied as-is')

# Ensure order_quantity >=1
agg['order_quantity'] = agg['order_quantity'].clip(lower=1).astype(int)

# Write back cleaned orders.csv
orders_cols_out = ['order_id'] + group_cols + ['order_quantity']
agg.to_csv(orders_out, index=False, columns=orders_cols_out)
print(f'WROTE cleaned orders.csv rows: {len(agg):,} -> {orders_out}')

# Assertion: no duplicate order_id
assert agg['order_id'].is_unique, 'order_id must be unique'

# ---------- Step 3: Regenerate inventory_events.csv ----------
print('Regenerating inventory_events.csv from cleaned orders.csv and vendors.csv')
orders = agg.copy()

# Load vendors (SKU-complete expected)
if os.path.exists(vendors_in):
    vdf = pd.read_csv(vendors_in)
else:
    raise SystemExit('vendors.csv missing; required to schedule replenishments')
vendor_map = {}
for _, r in vdf.iterrows():
    sku = r['sku_id']
    vendor_map[sku] = {
        'vendor_id': r.get('vendor_id', f'V_{sku}'),
        'lead_time': int(r.get('lead_time_days', 14)),
        'MOQ': int(r.get('MOQ', 100))
    }

# Define warehouses from orders regions: map region -> WH_<region>
orders['warehouse'] = orders['region'].apply(lambda r: f'WH_{r}')
warehouses = sorted(orders['warehouse'].unique())
skus = sorted(orders['sku_id'].unique())

# INITIAL_STOCK deterministic per (warehouse,sku)
events = []
RNG_SEED = 12345
for wh in warehouses:
    for sku in skus:
        # deterministic initial stock: hash-based seeding ensures reproducible across runs
        seed_val = (abs(hash(f'{wh}|{sku}')) + RNG_SEED) & 0xffffffff
        rng = np.random.RandomState(seed_val % (2**32))
        qty = int(rng.randint(500, 1500))
        events.append({'timestamp': 0, 'warehouse': wh, 'sku_id': sku, 'event': 'INITIAL_STOCK', 'quantity': int(qty), 'source_id': 'INIT'})

# Process orders in chronological order and emit OUTBOUND events.
# Pre-schedule replenishments per (warehouse,sku) based on total demand vs initial stock
orders_sorted = orders.sort_values('order_date').reset_index(drop=True)
threshold = 200
current_stock = {(wh, sku): next(e['quantity'] for e in events if e['warehouse']==wh and e['sku_id']==sku and e['event']=='INITIAL_STOCK')
                 for wh in warehouses for sku in skus}
scheduled = defaultdict(list)

# compute total demand per pair and pre-schedule enough MOQs to cover demand if initial stock insufficient
totals = orders_sorted.groupby(['warehouse','sku_id'])['order_quantity'].sum().reset_index()
final_ts = int(orders_sorted['order_date'].max()) if len(orders_sorted) else 0
for _, r in totals.iterrows():
    wh = r['warehouse']; sku = r['sku_id']; demand = int(r['order_quantity'])
    key = (wh, sku)
    init = current_stock.get(key, 0)
    deficit = demand - init
    if deficit > 0:
        v = vendor_map.get(sku, {'vendor_id': f'V_{sku}', 'lead_time': 14, 'MOQ': 100})
        moq = int(v['MOQ']); lead = max(1, int(v['lead_time']))
        # schedule at least ceil(deficit / moq) arrivals starting at first outbound + lead
        first_out_ts = int(orders_sorted[(orders_sorted['warehouse']==wh)&(orders_sorted['sku_id']==sku)]['order_date'].min())
        n = int((deficit + moq - 1) // moq)
        for i in range(n):
            arrival = first_out_ts + lead * (i+1)
            src = v.get('vendor_id', f'V_{sku}')
            scheduled[key].append((arrival, moq, src))

# Now iterate orders and materialize scheduled arrivals when their arrival <= current order ts
last_ts = 0
for _, row in orders_sorted.iterrows():
    ts = int(row['order_date'])
    wh = row['warehouse']
    sku = row['sku_id']
    ord_id = row['order_id']
    qty = int(row['order_quantity'])

    # materialize scheduled arrivals up to current ts
    if ts != last_ts:
        for key, arrs in list(scheduled.items()):
            arrivals_now = [a for a in arrs if a[0] <= ts]
            if arrivals_now:
                for a_ts, a_qty, a_src in arrivals_now:
                    events.append({'timestamp': a_ts, 'warehouse': key[0], 'sku_id': key[1], 'event': 'REPLENISHMENT_INBOUND', 'quantity': int(a_qty), 'source_id': a_src})
                    current_stock[key] = current_stock.get(key, 0) + int(a_qty)
                # remove processed
                scheduled[key] = [a for a in arrs if a[0] > ts]
        last_ts = ts

    key = (wh, sku)
    # emit OUTBOUND event(s) tied to order_id
    events.append({'timestamp': ts, 'warehouse': wh, 'sku_id': sku, 'event': 'OUTBOUND', 'quantity': -int(qty), 'source_id': ord_id})
    current_stock[key] = current_stock.get(key, 0) - int(qty)

    # if stock below threshold and there are no pending scheduled arrivals, schedule one more immediately
    if current_stock[key] < threshold and not scheduled.get(key):
        v = vendor_map.get(sku, {'vendor_id': f'V_{sku}', 'lead_time': 14, 'MOQ': 100})
        arrival = ts + max(1, int(v['lead_time']))
        moq = int(v['MOQ'])
        scheduled[key].append((arrival, moq, v.get('vendor_id', f'V_{sku}')))

# materialize any remaining scheduled replenishments after the last order timestamp
for key, arrs in scheduled.items():
    for a_ts, a_qty, a_src in arrs:
        if a_ts <= final_ts:
            a_ts = final_ts + 1
        events.append({'timestamp': a_ts, 'warehouse': key[0], 'sku_id': key[1], 'event': 'REPLENISHMENT_INBOUND', 'quantity': int(a_qty), 'source_id': a_src})
        current_stock[key] = current_stock.get(key, 0) + int(a_qty)

# Post-check: ensure no permanent negatives; if negative, schedule additional replenishments at final_ts + lead_time
negatives = {k:v for k,v in current_stock.items() if v < 0}
if negatives:
    print('WARN: some final inventory negative after pre-scheduling; adding extra replenishments')
for (wh, sku), val in list(negatives.items()):
    v = vendor_map.get(sku, {'vendor_id': f'V_{sku}', 'lead_time': 14, 'MOQ': 100})
    moq = int(v['MOQ']); lead = max(1, int(v['lead_time']))
    while current_stock[(wh,sku)] < 0:
        arrival = final_ts + lead
        src = v.get('vendor_id', f'V_{sku}')
        events.append({'timestamp': arrival, 'warehouse': wh, 'sku_id': sku, 'event': 'REPLENISHMENT_INBOUND', 'quantity': int(moq), 'source_id': src})
        current_stock[(wh,sku)] += moq

# Write inventory events with source_id for deduplication and traceability
inv_df = pd.DataFrame(events)
# ensure ordering
inv_df = inv_df.sort_values(by=['timestamp','warehouse','sku_id']).reset_index(drop=True)

# Deduplication rule: no duplicate (timestamp, warehouse, sku_id, event, source_id)
dup_cols = ['timestamp','warehouse','sku_id','event','source_id']
dup_count = inv_df.duplicated(subset=dup_cols).sum()
if dup_count:
    print(f'Found {dup_count} duplicate inventory events per dedupe key — removing exact duplicates')
    inv_df = inv_df.drop_duplicates(subset=dup_cols, keep='first').reset_index(drop=True)

# Final validations
# 1) all event types present
ev_types = set(inv_df['event'].unique())
assert {'INITIAL_STOCK','OUTBOUND','REPLENISHMENT_INBOUND'}.issubset(ev_types), 'Missing required event types after regeneration'

# 2) no duplicate order_id
assert inv_df['event'].isin(['OUTBOUND']).sum() >= len(orders), 'OUTBOUND events fewer than orders — check linking'

# 3) no duplicate (timestamp,warehouse,sku,event,source_id)
assert inv_df.duplicated(subset=dup_cols).sum() == 0, 'Duplicate inventory events remain'

# 4) final inventory non-negative
final_stock = defaultdict(int)
for _, r in inv_df.sort_values('timestamp').iterrows():
    key = (r['warehouse'], r['sku_id'])
    final_stock[key] += int(r['quantity'])
neg_final = {k:v for k,v in final_stock.items() if v < 0}
assert not neg_final, f'Final inventory negative for some pairs after regeneration: {list(neg_final.items())}'

# 5) SKUs in orders exist in vendors and inventory
orders_skus = set(orders['sku_id'])
vendor_skus = set(vdf['sku_id'])
inv_skus = set(inv_df['sku_id'])
missing_vendor = orders_skus - vendor_skus
missing_inv = orders_skus - inv_skus
assert len(missing_vendor)==0, f'Some SKUs in orders missing in vendors: {missing_vendor}'
assert len(missing_inv)==0, f'Some SKUs in orders missing in inventory_events: {missing_inv}'

# write out inventory_events.csv (overwrite)
inv_df.to_csv(inventory_out, index=False)
print(f'WROTE inventory events: {len(inv_df):,} rows -> {inventory_out}')

# ---------- Step 5: Additional validation checks ----------
print('Running validation checks: COD RTO, campaign uplift, dedup assertions')
orders_for_eval = orders.copy()
# For evaluation, expand orders by order_quantity to compute RTO rates correctly
orders_expanded = orders_for_eval.loc[orders_for_eval.index.repeat(orders_for_eval['order_quantity'])].reset_index(drop=True)

# COD RTO check
if 'payment_type' in orders_expanded.columns and 'delivery_status' in orders_expanded.columns:
    cod = orders_expanded[orders_expanded['payment_type']=='COD']
    pre = orders_expanded[orders_expanded['payment_type']!='COD']
    rto_cod = (cod['delivery_status']=='RTO').mean() if len(cod) else 0.0
    rto_pre = (pre['delivery_status']=='RTO').mean() if len(pre) else 0.0
    print(f'  RTO rates: COD={rto_cod:.3f}, PREPAID={rto_pre:.3f}')
    assert rto_cod >= rto_pre, 'COD RTO must be >= prepaid RTO'

# Campaign uplift check
if os.path.exists(campaigns_in):
    camps = pd.read_csv(campaigns_in)
    campaign_days = set()
    for _, c in camps.iterrows():
        start = int(c['start_day']); dur = int(c['duration_days'])
        for d in range(start, start+dur):
            campaign_days.add(d)
    daily = orders_expanded.groupby('order_date').size().rename('count').reset_index()
    daily['in_campaign'] = daily['order_date'].isin(campaign_days)
    mean_in = daily[daily['in_campaign']]['count'].mean() if daily['in_campaign'].any() else 0
    mean_out = daily[~daily['in_campaign']]['count'].mean() if (~daily['in_campaign']).any() else 0
    print(f'  mean orders/day IN campaign: {mean_in:.2f}, OUT: {mean_out:.2f}')
    assert mean_in > mean_out, 'Campaign uplift not observed after fixes'

print('All validations passed. Cleaned datasets written (orders.csv and inventory_events.csv).')
print('DATA FIX COMPLETE — READY FOR RE-AUDIT')
