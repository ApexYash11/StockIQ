from fastapi import APIRouter, Query, Request, HTTPException
from typing import Optional, List
from app import state

router = APIRouter()
@router.get("", tags=["COD"])
def list_cod(
    sku_id: Optional[str] = Query(None, description="Filter by SKU id (exact match)"),
    warehouse_id: Optional[str] = Query(None, description="Filter by warehouse_id (exact match)"),
):
    """Return COD intelligence rows. If no filters provided, returns all rows (caller beware)."""

    df = state.cod_df
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

    return df2.to_dict(orient="records")
@router.get("/decision", tags=["COD"])
def cod_decision(
    request: Request,
    sku_id: str = Query(..., description="SKU id (required, exact match)",),
    warehouse_id: str = Query(..., description="warehouse_id (required, exact match)"),
):
    """Return a single COD decision row identified by the full key (sku_id, warehouse_id)"""

    # Reject unexpected query params
    allowed = {"sku_id", "warehouse_id"}
    for k in request.query_params.keys():
        if k not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported query parameter: {k}")

    df = state.cod_df
    if df is None or df.empty:
        raise HTTPException(status_code=503, detail="COD data unavailable")

    # Validate artifact contains required columns
    if "sku_id" not in df.columns or "warehouse_id" not in df.columns:
        raise HTTPException(status_code=500, detail="Artifact missing required decision key columns")

    df2 = df.copy()
    sku_key = str(sku_id).strip()
    wh_key = str(warehouse_id).strip()

    mask = (df2["sku_id"].astype(str).str.strip() == sku_key) & (
        df2["warehouse_id"].astype(str).str.strip() == wh_key
    )

    matched = df2[mask]
    if matched.shape[0] == 0:
        raise HTTPException(status_code=404, detail="COD decision not found for the given key")
    if matched.shape[0] > 1:
        raise HTTPException(status_code=409, detail="Multiple COD decisions found for given key; artifact ambiguous")

    # Return the artifact row unchanged (dict with original column names)
    row = matched.iloc[0]
    return row.to_dict()
