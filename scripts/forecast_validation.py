"""
Standalone, deterministic end-to-end forecast validation script for StockIQ.
Follows the exact ordered steps requested by the user.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
# use Agg backend so script can run headless and save figures
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_percentage_error

# make behavior deterministic
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# project root (one level up from scripts/)
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_CSV = OUTPUT_DIR / 'orders.csv'

# --- Step 0: read data ---
if not ORDERS_CSV.exists():
    raise FileNotFoundError(f"orders.csv not found at {ORDERS_CSV}")

orders = pd.read_csv(ORDERS_CSV)
# ensure expected dtypes for safety
orders['order_date'] = orders['order_date'].astype(int)
orders['sku_id'] = orders['sku_id'].astype(str)
# cast campaign_applied to boolean (may be 0/1 or bool)
orders['campaign_applied'] = orders['campaign_applied'].astype(bool)

# --- Step 1: Global partial-week removal (CRITICAL) ---
# compute integer week index and count distinct days per week
orders['week'] = orders['order_date'] // 7
# count unique order_date values per week to detect partial weeks
days_per_week = orders.groupby('week')['order_date'].nunique().sort_index()
# drop weeks that do not contain exactly 7 distinct days
dropped_weeks = days_per_week[days_per_week != 7].index.tolist()
print('Dropped weeks (not exactly 7 distinct days):', dropped_weeks)
# keep only rows in full weeks
orders = orders[~orders['week'].isin(dropped_weeks)].copy()
# final safety check
remaining_days = orders.groupby('week')['order_date'].nunique()
assert (remaining_days == 7).all(), 'Partial weeks remain after filtering'
print('Step 1 complete: partial weeks removed. Weeks range:', remaining_days.index.min(), 'to', remaining_days.index.max())

# --- Step 2: Weekly aggregation ---
# First collapse to day-level per SKU+date to ensure campaign days counted once per day
day_level = (
    orders
    .groupby(['week', 'sku_id', 'order_date'], as_index=False)
    .agg({'order_quantity': 'sum', 'campaign_applied': 'max'})
)
# then aggregate to week+sku
weekly = (
    day_level
    .groupby(['week', 'sku_id'], as_index=False)
    .agg(weekly_qty=('order_quantity', 'sum'), campaign_days=('campaign_applied', 'sum'))
)
# campaign_intensity is the fraction of days in week with campaign active
weekly['campaign_intensity'] = weekly['campaign_days'] / 7.0
weekly.sort_values(['sku_id', 'week'], inplace=True)
print('Step 2 complete: weekly aggregation produced rows =', len(weekly))

# --- Step 3: Train / validation split (time-based) ---
weeks = sorted(weekly['week'].unique())
# use 80% of weeks for training, last 20% for validation
split_idx = int(len(weeks) * 0.8)
if split_idx < 1:
    split_idx = 1
train_weeks = weeks[:split_idx]
val_weeks = weeks[split_idx:]
assert len(val_weeks) > 0, 'Validation set is empty after split'
print('Train weeks:', len(train_weeks), 'Validation weeks:', len(val_weeks))

train_df = weekly[weekly['week'].isin(train_weeks)].copy()
val_df = weekly[weekly['week'].isin(val_weeks)].copy()

# --- Step 4: Baseline forecast (rolling mean) ---
WINDOW = 4
baseline = weekly.copy()
# rolling mean per SKU, min_periods=WINDOW ensures baseline only when full window exists
baseline['baseline'] = baseline.groupby('sku_id')['weekly_qty'].transform(lambda x: x.rolling(window=WINDOW, min_periods=WINDOW).mean())
# evaluate baseline only on validation weeks and where baseline exists
baseline_eval = baseline[baseline['week'].isin(val_weeks) & (~baseline['baseline'].isna())].copy()
print('Baseline evaluation samples:', len(baseline_eval))
if len(baseline_eval) > 0:
    baseline_mape = mean_absolute_percentage_error(baseline_eval['weekly_qty'], baseline_eval['baseline'])
else:
    baseline_mape = float('nan')
print('Baseline MAPE:', baseline_mape)

# --- Step 5: ML feature engineering ---
def make_features(df):
    df = df.copy()
    df.sort_values(['sku_id', 'week'], inplace=True)
    for lag in [1, 2, 4]:
        df[f'lag_{lag}'] = df.groupby('sku_id')['weekly_qty'].shift(lag)
    # seasonal features for yearly cycle
    df['sin_week'] = np.sin(2 * np.pi * df['week'] / 52)
    df['cos_week'] = np.cos(2 * np.pi * df['week'] / 52)
    return df

ml = make_features(weekly)
# drop rows missing lag values to prevent leakage and ensure consistent windows
ml.dropna(subset=['lag_1', 'lag_2', 'lag_4'], inplace=True)
train_ml = ml[ml['week'].isin(train_weeks)].copy()
val_ml = ml[ml['week'].isin(val_weeks)].copy()
assert len(train_ml) > 0 and len(val_ml) > 0, 'Train or validation ML set is empty after feature engineering'
print('Step 5 complete: train ML rows =', len(train_ml), 'val ML rows =', len(val_ml))

FEATURES = ['lag_1', 'lag_2', 'lag_4', 'campaign_intensity', 'sin_week', 'cos_week']
X_train, y_train = train_ml[FEATURES], train_ml['weekly_qty']
X_val, y_val = val_ml[FEATURES], val_ml['weekly_qty']

# --- Step 6: Train ML model ---
model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=RANDOM_STATE)
model.fit(X_train, y_train)
val_ml = val_ml.copy()
val_ml['p50'] = model.predict(X_val)
ml_mape = mean_absolute_percentage_error(y_val, val_ml['p50'])
print('ML MAPE:', ml_mape)

# --- Step 7: Uncertainty estimation — Quantile Regression approach ---
# Train two quantile regressors (0.1 and 0.9) on the same features used for P50.
# This directly models conditional quantiles (asymmetric intervals) without
# relying on Gaussian residual assumptions.
from sklearn.ensemble import GradientBoostingRegressor as GBR

# quantile models: deterministic by setting random_state
q10_model = GBR(loss='quantile', alpha=0.1, n_estimators=200, learning_rate=0.05, max_depth=3, random_state=RANDOM_STATE)
q90_model = GBR(loss='quantile', alpha=0.9, n_estimators=200, learning_rate=0.05, max_depth=3, random_state=RANDOM_STATE)

# fit on training ML features
q10_model.fit(X_train, y_train)
q90_model.fit(X_train, y_train)

# predict quantiles on validation set
val_ml['p10'] = q10_model.predict(X_val)
val_ml['p90'] = q90_model.predict(X_val)

def pinball_loss(y, y_pred, q):
    # quantile (pinball) loss for quantile q
    d = y - y_pred
    return np.mean(np.maximum(q * d, (q - 1) * d))

pinball_q10 = pinball_loss(y_val.values, val_ml['p10'].values, 0.1)
pinball_q90 = pinball_loss(y_val.values, val_ml['p90'].values, 0.9)
print(f'Pinball loss q=0.1: {pinball_q10:.6f}, q=0.9: {pinball_q90:.6f}')

# compute coverage of the [p10, p90] interval
coverage = ((val_ml['weekly_qty'] >= val_ml['p10']) & (val_ml['weekly_qty'] <= val_ml['p90'])).mean()
print(f'Coverage (P10-P90) on validation: {coverage:.3f}')

# --- Step 8: Diagnostics & plots ---
# choose example SKU with most validation rows (avoids hard-coding)
example_sku = val_ml['sku_id'].value_counts().idxmax()
print('Example SKU selected for plot:', example_sku)
# prepare plot frame combining train and validation rows for this SKU
plot_df = pd.concat([train_ml, val_ml], sort=False)
plot_df = plot_df[plot_df['sku_id'] == example_sku].sort_values('week')
plt.figure(figsize=(12, 6))
plt.plot(plot_df['week'], plot_df['weekly_qty'], label='Actual', marker='o')
if 'p50' in plot_df.columns:
    plt.plot(plot_df['week'], plot_df['p50'], label='P50 Forecast', marker='x')
if ('p10' in plot_df.columns) and ('p90' in plot_df.columns):
    # fill_between requires non-null ranges; use where both present
    p10 = plot_df['p10']
    p90 = plot_df['p90']
    if p10.notna().any() and p90.notna().any():
        plt.fill_between(plot_df['week'], p10, p90, color='C1', alpha=0.25, label='P10-P90')
plt.title(f'Weekly Demand — SKU {example_sku}')
plt.xlabel('Week')
plt.ylabel('Weekly units')
plt.legend()
plot_path = OUTPUT_DIR / f'forecast_{example_sku}.png'
plt.savefig(plot_path, bbox_inches='tight')
plt.close()
print('Plot saved to', plot_path)

# compute coverage on validation set where p10/p90 are present
coverage_mask = (val_ml['weekly_qty'] >= val_ml['p10']) & (val_ml['weekly_qty'] <= val_ml['p90'])
coverage = coverage_mask.mean() if len(coverage_mask) > 0 else float('nan')
print(f'Coverage (P10-P90) on validation: {coverage:.3f}')

# check for artificial last-week cliff for the example SKU: simple heuristic
sku_hist = plot_df.set_index('week')['weekly_qty']
weeks_sorted = sku_hist.index.values
if len(weeks_sorted) >= 2:
    last_train_weeks = sku_hist[sku_hist.index.isin(train_weeks)]
    first_val_weeks = sku_hist[sku_hist.index.isin(val_weeks)]
    if len(last_train_weeks) >= 1 and len(first_val_weeks) >= 1:
        prev = last_train_weeks.iloc[-1]
        first_val = first_val_weeks.iloc[0]
        if prev > 0 and (first_val / prev) < 0.1:
            print('Warning: potential last-week cliff detected for SKU', example_sku)

# --- Step 9: Final assertions ---
# assert no partial weeks remain
assert (orders.groupby('week')['order_date'].nunique() == 7).all(), 'Partial weeks detected in final check'
# compare ML vs baseline
if not np.isnan(baseline_mape):
    if ml_mape <= baseline_mape:
        print('ML model improved or matched baseline (ML MAPE <= Baseline MAPE)')
    else:
        print('Warning: ML MAPE > Baseline MAPE — investigate features/hyperparams')
else:
    print('Baseline MAPE not available (insufficient baseline evaluation samples)')
# coverage assertion
assert 0.70 <= coverage <= 0.95, f'Coverage {coverage:.3f} out of expected range [0.70,0.95]'
print('All final assertions passed')

print('FORECAST VALIDATION COMPLETE — UNCERTAINTY CALIBRATED')
