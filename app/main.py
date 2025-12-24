from fastapi import APIRouter, FastAPI, FastAPI
from app.loaders import load_artifacts
from app.routers import health, reorder, cod


app=FastAPI(title="StockIQ Reorder and COD Recommendation Service")

def startup_event():
    load_artifacts()

app.include_router(health.router)
app.include_router(reorder.router, prefix="/reorder")
app.include_router(cod.router, prefix="/cod")    