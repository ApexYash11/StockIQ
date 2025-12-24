from fastapi import FastAPI
from app.loaders import load_artifacts, load_models
from app.routers import reorder, cod, forecasts, models, diagnostics


app = FastAPI(title="StockIQ Reorder and COD Recommendation Service")


@app.on_event("startup")
def startup_event():
    # load CSV artifacts and model metadata at startup
    load_artifacts()
    load_models()


app.include_router(diagnostics.router)
app.include_router(reorder.router, prefix="/reorder")
app.include_router(cod.router, prefix="/cod")
app.include_router(forecasts.router, prefix="/forecasts")
app.include_router(models.router, prefix="/models")