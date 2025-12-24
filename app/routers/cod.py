from fastapi import APIRouter, Query
from typing import Optional, List
from app import state

router = APIRouter()


@router.get("", tags=["COD"])
def get_cod(
    sku_id: Optional[str] = Query(None),
    warehouse_id: Optional[str] = Query(None),
    cod_action: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    df = state.cod_df
    if df is None or df.empty:
        return []

    df2 = df.copy()
    if "sku_id" in df2.columns and sku_id is not None:
        sku_id = str(sku_id).strip()
        df2["sku_id"] = df2["sku_id"].astype(str).str.strip()
        df2 = df2[df2["sku_id"] == sku_id]

    if warehouse_id and "warehouse_id" in df2.columns:
        warehouse_id = str(warehouse_id).strip()
        df2["warehouse_id"] = df2["warehouse_id"].astype(str).str.strip()
        df2 = df2[df2["warehouse_id"] == warehouse_id]

    if cod_action and "cod_action" in df2.columns:
        cod_action = str(cod_action).strip()
        df2["cod_action"] = df2["cod_action"].astype(str).str.strip()
        df2 = df2[df2["cod_action"] == cod_action]
    elif cod_action and "cod_policy_action" in df2.columns:
        cod_action = str(cod_action).strip()
        df2["cod_policy_action"] = df2["cod_policy_action"].astype(str).str.strip()
        df2 = df2[df2["cod_policy_action"] == cod_action]

    if limit is not None:
        df2 = df2.head(limit)

    return df2.to_dict(orient="records")

@router.get("/decision", tags=["COD"])
def cod_decision(
    sku_id: str = Query(..., description="SKU id to lookup"),
    warehouse_id: Optional[str] = Query(None, description="Optional warehouse id; only used if present in artifact"),
):
    """Return a single COD decision row for `sku_id` and optional `Warehouse_id`.

    If the artifact does not contain a `lane` column, the lookup will be performed
    only by `sku_id`. Returns 404 if no matching row is found.
    """
    from fastapi import HTTPException

    df = state.cod_df
    if df is None or df.empty:
        raise HTTPException(status_code=503, detail="COD data unavailable")

    df2 = df.copy()
    # normalize sku
    if "sku_id" in df2.columns:
        df2["sku_id"] = df2["sku_id"].astype(str).str.strip()
    sku_key = str(sku_id).strip()
    mask = df2["sku_id"] == sku_key

    # only apply warehouse_id filter if column exists and warehouse_id provided
    if warehouse_id is not None and "warehouse_id" in df2.columns:
        warehouse_key = str(warehouse_id).strip()
        df2["warehouse_id"] = df2["warehouse_id"].astype(str).str.strip()
        mask = mask & (df2["warehouse_id"] == warehouse_key)

    row = df2[mask]
    if row.empty:
        raise HTTPException(status_code=404, detail="COD decision not found")

    r = row.iloc[0]

    # Map artifact columns to stable API field names
    return {
        "sku_id": r.get("sku_id"),
        "warehouse_id": r.get("warehouse_id") if "warehouse_id" in r.index else None,
        "historical_rto_rate": r.get("cod_rto_rate") if "cod_rto_rate" in r.index else None,
        "cod_share": r.get("cod_share") if "cod_share" in r.index else None,
        "cod_risk": r.get("cod_risk_bucket") if "cod_risk_bucket" in r.index else None,
        "cod_action": (
            r.get("cod_action")
            if "cod_action" in r.index
            else r.get("cod_policy_action")
            if "cod_policy_action" in r.index
            else None
        ),
        "notes": r.get("notes") if "notes" in r.index else None,
    }
