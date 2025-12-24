from fastapi import APIRouter, HTTPException, Query
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

    return df2.to_dict(orient="records")