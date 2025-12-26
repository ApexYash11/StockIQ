from fastapi import FastAPI
from app import state
from app.loaders import load_models
from app.routers import reorder, cod, forecast, models, diagnostics


app = FastAPI(title="StockIQ Decision Intelligence API")


@app.on_event("startup")
def startup_event():
    # Load CSV artifacts (authoritative offline artifacts) into `app.state`.
    # This loader is idempotent and only reads CSVs; it performs no business
    # logic or recomputation. Models metadata is loaded separately.
    state.load_artifacts()
    load_models()


# Expose lightweight diagnostic and artifact-serving routers. Prefixes are
# intentionally simple so dashboards and OMS systems can call predictable URLs.
app.include_router(diagnostics.router)
app.include_router(reorder.router, prefix="/reorder")
app.include_router(cod.router, prefix="/cod")
app.include_router(forecast.router, prefix="/forecast")
app.include_router(models.router, prefix="/models")