# app/routers/cod.py
from fastapi import APIRouter, HTTPException, Query
from app import state
from app.schema import CODDecision

router = APIRouter(prefix="/cod")

@router.get("/decision", response_model=CODDecision)
def cod_decision(
    sku_id: str = Query(...),
    lane: str = Query(...)
):
    df = state.cod_df

    if df is None:
        raise HTTPException(status_code=503, detail="COD data unavailable")

    row = df[
        (df["sku_id"] == sku_id) &
        (df["lane"] == lane)
    ]

    if row.empty:
        raise HTTPException(status_code=404, detail="COD decision not found")

    r = row.iloc[0]

    return {
        "sku_id": r["sku_id"],
        "lane": r["lane"],
        "cod_risk": r["cod_risk"],
        "cod_action": r["cod_action"],
        "explanation": r["explanation"]
    }
