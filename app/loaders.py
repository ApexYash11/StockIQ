import json
import os
import pandas as pd
from pathlib import Path
from app import state

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))


def _read_csv_safe(path: Path):
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


# Initialize safe defaults at module import time so `state` is always defined.
state.reorder_df = pd.DataFrame()
state.cod_df = pd.DataFrame()
state.metadata = {}


def load_artifacts(artifacts_dir: Path | str | None = None):
    """Load artifacts into `app.state`.

    This function is intentionally idempotent and safe to call at startup or on reloads.
    It prefers existing CSV filenames present in the `artifacts/` directory.
    """
    global ARTIFACTS_DIR
    if artifacts_dir is not None:
        ARTIFACTS_DIR = Path(artifacts_dir)

    # Reorder recommendations
    reorder_path = ARTIFACTS_DIR / "reorder_recommendations.csv"
    state.reorder_df = _read_csv_safe(reorder_path)

    # Forecasts
    forecast_path = ARTIFACTS_DIR / "weekly_forecast_future.csv"
    state.forecast_df = _read_csv_safe(forecast_path)

    # COD intelligence: prefer `cod_recommendations.csv` but fall back to `cod_intelligence.csv`
    cod_path = ARTIFACTS_DIR / "cod_recommendations.csv"
    alt_cod_path = ARTIFACTS_DIR / "cod_intelligence.csv"
    if cod_path.exists():
        state.cod_df = _read_csv_safe(cod_path)
    else:
        state.cod_df = _read_csv_safe(alt_cod_path)

    # Optional metadata
    metadata_path = ARTIFACTS_DIR / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, "r") as f:
                state.metadata = json.load(f)
        except Exception:
            state.metadata = {}
    else:
        state.metadata = {}

    # compute simple metadata
    meta = {
        "reorder_rows": len(state.reorder_df),
        "cod_rows": len(state.cod_df),
        "forecast_rows": len(state.forecast_df),
    }
    state.metadata = {**(state.metadata or {}), **meta}
    return meta


def load_models(models_dir: Path | str | None = None):
    """Inspect and register PKL models as metadata in `state.models`.

    This function does NOT execute or expose model objects. It only records
    filename, path, mtime, sha256 and an inferred type string.
    """
    import hashlib
    import pickle

    models_path = Path(models_dir) if models_dir is not None else Path("notebooks/models")
    models_meta = {}
    if not models_path.exists():
        state.models = models_meta
        return models_meta

    for p in models_path.glob("*.pkl"):
        try:
            raw = p.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            mtime = p.stat().st_mtime
            size = p.stat().st_size
            obj = None
            safe_type = "unknown"
            try:
                with open(p, "rb") as f:
                    obj = pickle.load(f)
                safe_type = type(obj).__name__
            except Exception:
                obj = None
                safe_type = "unloadable"

            models_meta[p.name] = {
                "path": str(p),
                "mtime": mtime,
                "sha256": sha,
                "size": size,
                "type": safe_type,
                "loadable": obj is not None,
            }
        except Exception:
            continue

    state.models = models_meta
    return models_meta