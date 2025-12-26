from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from typing import Optional, List
from app import state
from app.schema import ReorderRecommendation

router = APIRouter()


@router.get("", response_model=List[ReorderRecommendation], tags=["Reorder"])
def get_reorder(
    sku_id: Optional[str] = Query(None, description="Filter by SKU ID"),
    warehouse_id: Optional[str] = Query(None, description="Filter by Warehouse ID"),
):
    """Endpoint to retrieve reorder recommendations.

    Notes:
    - Query parameters are normalized (trimmed) to tolerate URL-encoded whitespace (e.g. `%09`).
    - DataFrame comparisons use string strip to avoid mismatches from stray whitespace.
    """
    df = state.reorder_df

    # If the dataframe is not yet populated, return empty list (server still warming)
    if df is None or df.empty:
        return []

    # normalize incoming filters
    if sku_id is not None:
        sku_id = str(sku_id).strip()
    if warehouse_id is not None:
        warehouse_id = str(warehouse_id).strip()

    # Work on a copy and normalize dataframe string columns used for filtering
    df2 = df.copy()
    if "sku_id" in df2.columns:
        df2["sku_id"] = df2["sku_id"].astype(str).str.strip()
    if "warehouse_id" in df2.columns:
        df2["warehouse_id"] = df2["warehouse_id"].astype(str).str.strip()

    if sku_id:
        df2 = df2[df2["sku_id"] == sku_id]

    if warehouse_id:
        df2 = df2[df2["warehouse_id"] == warehouse_id]

    # Deduplicate rows by (sku_id, warehouse_id), keeping the latest `run_date` when available.
    # This ensures callers receive a single decision row per SKU×warehouse.
    if not df2.empty:
        if "run_date" in df2.columns:
            try:
                df2["_run_date_parsed"] = pd.to_datetime(df2["run_date"], errors="coerce")
                df2 = df2.sort_values("_run_date_parsed", ascending=False)
                df2 = df2.drop_duplicates(subset=["sku_id", "warehouse_id"], keep="first")
                df2 = df2.drop(columns=["_run_date_parsed"])
            except Exception:
                # fall back to first-occurrence dedupe if parsing fails
                df2 = df2.drop_duplicates(subset=["sku_id", "warehouse_id"], keep="first")
        else:
            df2 = df2.drop_duplicates(subset=["sku_id", "warehouse_id"], keep="first")

    # Build strict response objects that match the ReorderRecommendation schema
    records = []
    for _, row in df2.iterrows():
        # Preserve original CSV columns but also compute required, frontend-safe fields
        inventory_position = row.get("on_hand")
        expected_demand_LT = row.get("lead_time_demand")
        reorder_point = row.get("reorder_point")

        # Compute reorder_required using the specified inventory logic
        reorder_required = False
        try:
            # numeric comparison; if any value missing, default to False (no reorder)
            if inventory_position is not None and reorder_point is not None:
                reorder_required = float(inventory_position) <= float(reorder_point)
        except Exception:
            reorder_required = False

        sku_status = "REORDER" if reorder_required else "OK"

        # Human-readable decision reason
        if reorder_required:
            decision_reason = (
                f"Inventory ({inventory_position}) <= reorder_point ({reorder_point}) -> REORDER"
            )
        else:
            decision_reason = (
                f"Inventory ({inventory_position}) > reorder_point ({reorder_point}) -> OK"
            )

        # recommended_order_qty maps to CSV's recommended_reorder_qty when present
        recommended_order_qty = None
        if "recommended_order_qty" in row.index:
            recommended_order_qty = row.get("recommended_order_qty")
        if recommended_order_qty is None and "recommended_reorder_qty" in row.index:
            recommended_order_qty = row.get("recommended_reorder_qty")

        # demand_source is explicit and stable for frontend consumers
        demand_source = "forecast_v1"

        rec = {
            "sku_id": row.get("sku_id"),
            "warehouse_id": row.get("warehouse_id"),
            "demand_source": demand_source,
            "inventory_position": inventory_position,
            "expected_demand_LT": expected_demand_LT,
            "safety_stock": row.get("safety_stock"),
            "reorder_point": reorder_point,
            "reorder_required": reorder_required,
            "recommended_order_qty": recommended_order_qty,
            "sku_status": sku_status,
            "decision_reason": decision_reason,
            "run_date": row.get("run_date"),
        }

        records.append(rec)

    return records