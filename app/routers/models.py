from fastapi import APIRouter, HTTPException
from app import state

router = APIRouter()


@router.get("", tags=["Models"])
def list_models():
    meta = state.models or {}
    return meta


@router.get("/{model_name}", tags=["Models"])
def get_model_metadata(model_name: str):
    meta = state.models or {}
    if model_name not in meta:
        raise HTTPException(status_code=404, detail="model not found")
    return meta[model_name]
