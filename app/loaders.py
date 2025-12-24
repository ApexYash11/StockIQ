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

    return {
        "reorder_rows": len(state.reorder_df),
        "cod_rows": len(state.cod_df),
    }