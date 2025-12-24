from fastapi import APIRouter, Query
from typing import Optional, List
from app import state

router = APIRouter()


@router.get("", tags=["Forecasts"])
def get_forecasts(
    sku_id: Optional[str] = Query(None),
    start_week: Optional[str] = Query(None),
    end_week: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    """Serve rows from weekly_forecast_future.csv. Filtering is deterministic only."""
    df = state.forecast_df
    if df is None or df.empty:
        return []

    df2 = df.copy()
    if sku_id is not None:
        sku_id = str(sku_id).strip()
        if "sku_id" in df2.columns:
            df2["sku_id"] = df2["sku_id"].astype(str).str.strip()
            df2 = df2[df2["sku_id"] == sku_id]

    # week filtering: try to apply if a week column exists
    week_cols = [c for c in df2.columns if "week" in c.lower() or "date" in c.lower()]
    if start_week and week_cols:
        col = week_cols[0]
        df2 = df2[df2[col] >= start_week]
    if end_week and week_cols:
        col = week_cols[0]
        df2 = df2[df2[col] <= end_week]

    if limit is not None:
        df2 = df2.head(limit)

    return df2.to_dict(orient="records")
