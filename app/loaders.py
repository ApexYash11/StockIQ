import json
import os
import pandas as pd
from pathlib import Path
from app import state


def load_artifacts(artifacts_dir: Path | str | None = None):
    """Compatibility shim: delegate artifact loading to `app.state.load_artifacts()`.

    We keep this function to avoid breaking existing callers that import
    `load_artifacts` from `app.loaders`. The canonical implementation now
    lives in `app.state`.
    """
    return state.load_artifacts(artifacts_dir)


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