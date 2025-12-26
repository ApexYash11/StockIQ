from fastapi import APIRouter, Query, Request, HTTPException
from typing import Optional, List
from app import state

router = APIRouter()


@router.get("", tags=["Forecast"])
def list_forecasts(
    sku_id: Optional[str] = Query(None, description="Filter by SKU id (exact match)",placeholder="SKU0001"),
    warehouse_id: Optional[str] = Query(None, description="Optional warehouse id filter",placeholder="north"),
    week: Optional[str] = Query(None, description="Filter by week identifier/date string",placeholder="2025-02-10"),
    limit: Optional[int] = Query(None, description="Limit number of returned rows",placeholder=10),
):
    """Return rows from the authoritative forecasts artifact.

    Purpose: expose the offline probabilistic forecasts (p10/p50/p90 and metadata)
    so dashboards and downstream systems can read forecasts without recomputation.
    This endpoint performs only deterministic filtering and returns artifact rows
    unchanged (aside from column-name normalization applied at load time).
    """
    df = state.forecast_df
    if df is None or df.empty:
        return []

    df2 = df.copy()

    if sku_id is not None:
        sku = str(sku_id).strip()
        if "sku_id" in df2.columns:
            df2 = df2[df2["sku_id"].astype(str).str.strip() == sku]

    if warehouse_id is not None:
        wh = str(warehouse_id).strip()
        if "warehouse_id" in df2.columns:
            df2 = df2[df2["warehouse_id"].astype(str).str.strip() == wh]

    if week is not None:
        # Attempt to find a reasonable week/date column and apply equality
        week_cols = [c for c in df2.columns if "week" in c or "date" in c]
        if week_cols:
            col = week_cols[0]
            df2 = df2[df2[col].astype(str).str.strip() == str(week).strip()]

    if limit is not None:
        df2 = df2.head(limit)

    return df2.to_dict(orient="records")


@router.get("/decision", tags=["Forecast"])
def forecast_decision(request: Request, sku_id: str = Query(...), week: str = Query(...)):
    """Return a single authoritative forecast row for `sku_id` at `week`.

    Purpose: answer the business question "What is the canonical forecast
    (p10/p50/p90) for this SKU and week?". This endpoint enforces exact-key
    lookup and returns 404/409 where appropriate. No computation is performed.
    """
    # Enforce strict query params so responses are deterministic
    allowed = {"sku_id", "week"}
    for k in request.query_params.keys():
        if k not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported query parameter: {k}")

    df = state.forecast_df
    if df is None or df.empty:
        raise HTTPException(status_code=503, detail="Forecast data unavailable")

    # determine week/date column
    week_cols = [c for c in df.columns if "week" in c or "date" in c]
    if not week_cols:
        raise HTTPException(status_code=500, detail="Forecast artifact missing a week/date column")
    week_col = week_cols[0]

    if "sku_id" not in df.columns:
        raise HTTPException(status_code=500, detail="Forecast artifact missing `sku_id` column")

    sku_key = str(sku_id).strip()
    week_key = str(week).strip()

    df2 = df.copy()
    mask = (df2["sku_id"].astype(str).str.strip() == sku_key) & (
        df2[week_col].astype(str).str.strip() == week_key
    )
    matched = df2[mask]
    if matched.shape[0] == 0:
        raise HTTPException(status_code=404, detail="Forecast not found for given key")
    if matched.shape[0] > 1:
        raise HTTPException(status_code=409, detail="Multiple forecast rows found; artifact ambiguous")

    return matched.iloc[0].to_dict()
