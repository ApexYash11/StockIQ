import os
import json
import pandas as pd
import numpy as np
from collections import Counter

base_dir = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.abspath(os.path.join(base_dir, '..', 'output'))
paths = {
    'orders': os.path.join(out_dir, 'orders.csv'),
    'inventory': os.path.join(out_dir, 'inventory_events.csv'),
    'vendors': os.path.join(out_dir, 'vendors.csv'),
    'campaigns': os.path.join(out_dir, 'campaigns.csv'),
}

print('\n=== STOCKIQ DATA AUDIT ===\n')

# Helper to safely read
def safe_read_csv(path, **kwargs):
    if not os.path.exists(path):
        print(f'MISSING FILE: {path}')
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception as e:
        print(f'ERROR reading {path}: {e}')
        return None

# Read small samples / essential cols
orders = safe_read_csv(paths['orders'])
inv = safe_read_csv(paths['inventory'])
vendors = safe_read_csv(paths['vendors'])
campaigns = safe_read_csv(paths['campaigns'])

# Step 1 - Structural Validation
print('\n**Step 1 — Structural Validation**')

def schema_report(df, name):
    if df is None:
        print(f'- {name}: MISSING')
        return
    print(f'- {name}: rows={len(df):,}, cols={list(df.columns)}')
    print('  dtypes:')
    print(df.dtypes.to_string())
    nulls = df.isnull().sum()
    nulls = nulls[nulls>0]
    if len(nulls):
        print('  nulls:')
        print(nulls.to_string())
    else:
        print('  nulls: none')
    # duplicates
    dup = df.duplicated().sum()
    print(f'  duplicate rows: {dup}')

schema_report(orders, 'orders.csv')
schema_report(inv, 'inventory_events.csv')
schema_report(vendors, 'vendors.csv')
schema_report(campaigns, 'campaigns.csv')

# Cardinality expectations
print('\n- Cardinality check (orders >> inventory_events > vendors >> campaigns):')
orders_n = len(orders) if orders is not None else 0
inv_n = len(inv) if inv is not None else 0
vendors_n = len(vendors) if vendors is not None else 0
campaigns_n = len(campaigns) if campaigns is not None else 0
print(f'  orders={orders_n:,}, inventory_events={inv_n:,}, vendors={vendors_n:,}, campaigns={campaigns_n:,}')

# Quick pass/fail
card_ok = orders_n > inv_n and inv_n >= vendors_n and vendors_n >= campaigns_n
print('  status:', 'PASS' if card_ok else 'WARN')

# Step 2 - Cross-file consistency
print('\n**Step 2 — Cross-File Consistency Checks**')
problems = []
if orders is not None:
    skus_orders = set(orders['sku_id'].dropna().unique())
else:
    skus_orders = set()
if vendors is not None:
    skus_vendors = set(vendors['sku_id'].dropna().unique())
else:
    skus_vendors = set()
if inv is not None:
    skus_inv = set(inv['sku_id'].dropna().unique())
else:
    skus_inv = set()

missing_in_vendors = sorted(list(skus_orders - skus_vendors))
missing_in_inventory = sorted(list(skus_orders - skus_inv))
print(f'- SKUs in orders: {len(skus_orders)}; missing in vendors: {len(missing_in_vendors)}; missing in inventory: {len(missing_in_inventory)}')
if missing_in_vendors:
    print('  sample missing in vendors:', missing_in_vendors[:5])
    problems.append(('vendors.csv','sku_id','SKUs present in orders missing in vendors.csv','Run `generate_vendors.py` to ensure one vendor per SKU'))
if missing_in_inventory:
    print('  sample missing in inventory:', missing_in_inventory[:5])
    problems.append(('inventory_events.csv','sku_id','SKUs present in orders missing in inventory_events.csv','Regenerate inventory events or ensure OUTBOUND events emitted for all SKUs'))

# Warehouses consistency: inventory warehouses vs order regions
if inv is not None:
    whs_inv = set(inv['warehouse'].dropna().unique())
else:
    whs_inv = set()
if orders is not None and 'region' in orders.columns:
    regions = set(orders['region'].dropna().unique())
else:
    regions = set()
print(f'- warehouses in inventory: {sorted(list(whs_inv))[:10]}')
print(f'- regions in orders: {sorted(list(regions))[:10]}')
# heuristic: check warehouse names prefixed with WH_<region>
region_like_wh = set(['WH_'+r for r in regions])
unknown_wh = sorted(list(whs_inv - region_like_wh))
if unknown_wh:
    print('  WARN: inventory has warehouses not matching WH_<region> from orders regions sample:', unknown_wh[:5])

# Campaign windows overlap orders
if campaigns is not None and orders is not None:
    min_order = int(orders['order_date'].min())
    max_order = int(orders['order_date'].max())
    print(f'- orders order_date range: {min_order} to {max_order}')
    overlaps = 0
    for _, c in campaigns.iterrows():
        start = int(c['start_day'])
        end = start + int(c['duration_days']) - 1
        if end < min_order or start > max_order:
            print(f'  WARN: campaign {c.get("campaign_id","? ")} window {start}-{end} outside orders range')
        else:
            overlaps += 1
    print(f'  campaigns overlapping orders: {overlaps} / {len(campaigns)}')

# Vendors validity
if vendors is not None:
    bad_lead = vendors[(vendors['lead_time_days'] < 7) | (vendors['lead_time_days'] > 30)]
    bad_moq = vendors[~vendors['MOQ'].isin([50,100,200])] if 'MOQ' in vendors.columns else pd.DataFrame()
    print(f"- vendors lead_time anomalies: {len(bad_lead)}; bad MOQ: {len(bad_moq)}")
    if len(bad_lead):
        problems.append(('vendors.csv','lead_time_days','lead_time_days out of expected range 7-30','Regenerate vendors with proper lead_time_days range'))
    if len(bad_moq):
        problems.append(('vendors.csv','MOQ','MOQ not in {50,100,200}','Fix MOQ generation'))

# Step 3 - Inventory logic validation
print('\n**Step 3 — Inventory Logic Validation**')
if inv is None:
    print('inventory_events.csv missing — FAIL')
else:
    ev_types = set(inv['event'].dropna().unique())
    print(f'- event types present: {ev_types}')
    required = {'INITIAL_STOCK','OUTBOUND','REPLENISHMENT_INBOUND'}
    missing_ev = required - ev_types
    print(f'- required event types missing: {missing_ev}')
    if missing_ev:
        problems.append(('inventory_events.csv','event','missing required event types','Ensure generator emits all required event types'))

    # reconstruct running inventory for each (warehouse,sku) but limit to small sample to keep memory use reasonable
    pairs = inv[['warehouse','sku_id']].drop_duplicates().head(200)
    negative_final = []
    late_replenishments = []
    for _, r in pairs.iterrows():
        wh, sku = r['warehouse'], r['sku_id']
        df = inv[(inv['warehouse']==wh)&(inv['sku_id']==sku)].sort_values(by='timestamp')
        run = 0
        # sum quantities sequentially
        for _, e in df.iterrows():
            run += int(e['quantity'])
        if run < 0:
            negative_final.append(((wh,sku), run))
        # check replenishment timestamps > earliest outbound
        out_ts = df[df['event']=='OUTBOUND']['timestamp']
        rep_ts = df[df['event']=='REPLENISHMENT_INBOUND']['timestamp']
        if len(rep_ts) and len(out_ts) and (rep_ts.min() <= out_ts.min()):
            late_replenishments.append((wh,sku))
    print(f'- sample negative_final count: {len(negative_final)} (show up to 5): {negative_final[:5]}')
    print(f'- sample replenishment timing issues: {len(late_replenishments)} (show up to 5): {late_replenishments[:5]}')
    if negative_final:
        problems.append(('inventory_events.csv','quantity','final negative inventory for some (warehouse,sku) in sample','Ensure replenishments cover demand or adjust MOQ/lead times'))
    if late_replenishments:
        problems.append(('inventory_events.csv','timestamp','REPLENISHMENT_INBOUND occurs before OUTBOUND for some sample pairs','Verify scheduling logic for replenishments'))

# Step 4 - Demand & Campaign Realism
print('\n**Step 4 — Demand & Campaign Realism**')
if orders is None or campaigns is None:
    print('orders.csv or campaigns.csv missing — cannot evaluate')
else:
    daily = orders.groupby('order_date').size().rename('count').reset_index()
    # compute campaign days set
    camp_days = set()
    for _, c in campaigns.iterrows():
        s = int(c['start_day']); d = int(c['duration_days'])
        for day in range(s, s+d):
            camp_days.add(day)
    daily['in_campaign'] = daily['order_date'].isin(camp_days)
    mean_in = daily[daily['in_campaign']==True]['count'].mean() if daily['in_campaign'].any() else 0
    mean_out = daily[daily['in_campaign']==False]['count'].mean() if (~daily['in_campaign']).any() else 0
    print(f'- mean orders per day IN campaign: {mean_in:.2f}; OUT of campaign: {mean_out:.2f}')
    if mean_in > mean_out:
        print('  PASS: campaign uplift visible')
    else:
        print('  WARN: no uplift detected')
        problems.append(('campaigns.csv','start_day/duration/uplift','no detectable uplift in orders over campaign windows','Ensure campaigns are applied to orders and uplift applied at generation time'))

# Step 5 - COD / RTO Sanity Checks
print('\n**Step 5 — COD / RTO Sanity Checks**')
if orders is not None and 'payment_type' in orders.columns and 'delivery_status' in orders.columns:
    cod = orders[orders['payment_type']=='COD']
    pre = orders[orders['payment_type']!='COD']
    rto_cod = (cod['delivery_status']=='RTO').mean() if len(cod) else float('nan')
    rto_pre = (pre['delivery_status']=='RTO').mean() if len(pre) else float('nan')
    print(f'- RTO COD={rto_cod:.3f}; prepaid={rto_pre:.3f}')
    if rto_cod >= rto_pre:
        print('  PASS: COD RTO >= prepaid RTO')
    else:
        print('  FAIL: COD RTO < prepaid RTO')
        problems.append(('orders.csv','delivery_status/payment_type','COD RTO rate lower than prepaid','Adjust RTO sampling to ensure COD has higher RTO'))
else:
    print('  WARN: payment_type or delivery_status missing; cannot evaluate')

# Step 6 - ML Readiness Assessment
print('\n**Step 6 — ML Readiness Assessment**')
ml_issues = []
if orders is None:
    print('- orders.csv missing — FAIL')
    ml_issues.append('orders.csv missing')
else:
    req_cols = ['order_date','sku_id']
    for c in req_cols:
        if c not in orders.columns:
            ml_issues.append(f'missing {c} in orders.csv')
    # check for time series continuity
    days = sorted(orders['order_date'].unique())
    if len(days):
        gap = max(days) - min(days) + 1
        coverage = len(days) / gap
        print(f'- time series day coverage: {coverage:.3f} (1.0 = contiguous)')
        if coverage < 0.5:
            ml_issues.append('sparse day coverage; may hinder forecasting')

    # check features for RTO prediction
    feat_cols = ['payment_type','delivery_days']
    missing_feats = [c for c in feat_cols if c not in orders.columns]
    if missing_feats:
        ml_issues.append(f'missing features for RTO prediction: {missing_feats}')

print('\nSummary of problems (first 10):')
if problems:
    for p in problems[:10]:
        print('-', p)
else:
    print('No problems detected')

print('\nAudit complete')
