from fastapi import APIRouter
from app import state
import time

router = APIRouter()


@router.get("/health", tags=["Diagnostics"])
def health():
    return {"status": "ok", "time": time.time()}


@router.get("/ready", tags=["Diagnostics"])
def ready():
    # ready if reorder and forecast artifacts loaded
    ready_ok = True
    errors = []
    if state.reorder_df is None or state.reorder_df.empty:
        ready_ok = False
        errors.append("reorder_recommendations missing or empty")
    # forecast optional
    return {"ready": ready_ok, "errors": errors}


@router.get("/metadata", tags=["Diagnostics"])
def metadata():
    meta = state.metadata or {}
    # augment with artifact rows
    meta_out = meta.copy() if isinstance(meta, dict) else {}
    meta_out.setdefault("artifacts", {})
    meta_out["artifacts"]["reorder_recommendations.csv"] = {"rows": len(state.reorder_df) if state.reorder_df is not None else 0}
    meta_out["artifacts"]["weekly_forecast_future.csv"] = {"rows": len(state.forecast_df) if getattr(state, 'forecast_df', None) is not None else 0}
    meta_out["models"] = state.models or {}
    return meta_out
