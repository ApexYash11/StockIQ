from fastapi import APIRouter
from app import state

router = APIRouter()

@router.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify that the service is running.
    """
    return {
        "status": "healthy",
        "metadata": state.metadata,
        "artifacts_loaded": state.reorder_df is not None and state.cod_df is not None 
    }

@router.get("/metadata", tags=["Health"])
async def get_metadata():
    """
    Endpoint to retrieve metadata about the loaded artifacts.
    """
    if state.metadata is None:
        return {"error": "Metadata not loaded"}
    return state.metadata     