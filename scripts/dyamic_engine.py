"""
Dynamic, multi-SKU inventory reorder engine for StockIQ.

- Routes SKUs by maturity
- Uses different demand estimation strategies
- Computes reorder points & quantities
- Produces deterministic, NaN-free output
"""

import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)

# =====================================================
# STEP 0 — LOAD ARTIFACTS (FORECAST)
# =====================================================

FORECAST_PATH = Path("./artifacts/weekly_forecast_future.csv")

if FORECAST_PATH.exists():
    forecast_df = pd.read_csv(FORECAST_PATH)
else:
    # Fallback mock forecast (for first run)
    forecast_df = pd.DataFrame({
        "sku_id": ["SKU0001"] * 4,
        "week": [104, 105, 106, 107],
        "p10": [400, 410, 420, 430],
        "p50": [450, 460, 470, 480],
        "p90": [520, 530, 540, 550],
    })

forecast_df.sort_values(["sku_id", "week"], inplace=True)

# =====================================================
# STEP 1 — INVENTORY & VENDOR CONTEXT
# =====================================================

inventory = pd.DataFrame({
    "sku_id": ["SKU0001", "SKU0002", "SKU0003"],
    "warehouse_id": ["WH1", "WH1", "WH2"],
    "on_hand": [420, 120, 60],
    "on_order": [200, 0, 0],
})

vendors = pd.DataFrame({
    "sku_id": ["SKU0001", "SKU0002", "SKU0003"],
    "lead_time_weeks": [2, 3, 1],
    "MOQ": [500, 300, 200],
})

# =====================================================
# STEP 2 — SKU ROUTING (POLICY LAYER)
# =====================================================

def route_sku(history_weeks: int) -> str:
    if history_weeks >= 60:
        return "SARIMAX"
    elif history_weeks >= 12:
        return "ML_BASELINE"
    else:
        return "NAIVE"

# Derive history length
sku_history = (
    forecast_df.groupby("sku_id")["week"]
    .count()
    .rename("history_weeks")
    .reset_index()
)

context = (
    inventory
    .merge(vendors, on="sku_id", how="left")
    .merge(sku_history, on="sku_id", how="left")
)

context["history_weeks"] = context["history_weeks"].fillna(0)
context["forecast_strategy"] = context["history_weeks"].apply(route_sku)
context["inventory_position"] = context["on_hand"] + context["on_order"]

# =====================================================
# STEP 3 — DEMAND ESTIMATION STRATEGIES
# =====================================================

def demand_from_forecast(forecast_df, sku_id, lead_time_weeks):
    df = forecast_df[forecast_df["sku_id"] == sku_id].head(lead_time_weeks)
    return {
        "expected_demand_LT": df["p50"].sum(),
        "safety_stock": df["p90"].sum() - df["p50"].sum(),
        "source": "SARIMAX"
    }

def demand_from_history(sku_id, lead_time_weeks):
    WEEKLY_AVG = 200  # mock baseline
    return {
        "expected_demand_LT": WEEKLY_AVG * lead_time_weeks,
        "safety_stock": WEEKLY_AVG * 0.3 * lead_time_weeks,
        "source": "ML_BASELINE"
    }

def demand_for_new_sku(lead_time_weeks):
    DEFAULT_WEEKLY = 100
    return {
        "expected_demand_LT": DEFAULT_WEEKLY * lead_time_weeks,
        "safety_stock": DEFAULT_WEEKLY * 0.5 * lead_time_weeks,
        "source": "NAIVE"
    }

def resolve_demand(row):
    if row["forecast_strategy"] == "SARIMAX":
        return demand_from_forecast(
            forecast_df,
            row["sku_id"],
            row["lead_time_weeks"]
        )
    elif row["forecast_strategy"] == "ML_BASELINE":
        return demand_from_history(
            row["sku_id"],
            row["lead_time_weeks"]
        )
    else:
        return demand_for_new_sku(row["lead_time_weeks"])

# =====================================================
# STEP 4 — REORDER ENGINE (DYNAMIC, MULTI-SKU)
# =====================================================

results = []

for _, row in context.iterrows():
    demand = resolve_demand(row)

    reorder_point = (
        demand["expected_demand_LT"] +
        demand["safety_stock"]
    )

    reorder_required = row["inventory_position"] <= reorder_point

    gap = reorder_point - row["inventory_position"]
    recommended_qty = (
        max(row["MOQ"], int(np.ceil(gap / row["MOQ"]) * row["MOQ"]))
        if reorder_required else 0
    )

    results.append({
        "sku_id": row["sku_id"],
        "strategy_used": demand["source"],
        "inventory_position": row["inventory_position"],
        "expected_demand_LT": round(demand["expected_demand_LT"], 2),
        "safety_stock": round(demand["safety_stock"], 2),
        "reorder_point": round(reorder_point, 2),
        "reorder_required": reorder_required,
        "recommended_order_qty": recommended_qty
    })

final_df = pd.DataFrame(results)

# =====================================================
# STEP 5 — OUTPUT
# =====================================================

print("\n=== DYNAMIC REORDER ENGINE OUTPUT ===\n")
print(final_df)

# Optional save
Path("./artifacts").mkdir(exist_ok=True)
final_df.to_csv("./artifacts/reorder_recommendations_dynamic.csv", index=False)

print("\nSaved to ./artifacts/reorder_recommendations_dynamic.csv")
