from typing import Optional
import os
from pathlib import Path
import pandas as pd

# Public module state used by routers. These are populated by `load_artifacts()` at
# application startup. The server MUST treat these dataframes as the single
# source-of-truth for responses — endpoints should only filter/return rows and
# must not implement business logic or recompute recommendations.
reorder_df: Optional[pd.DataFrame] = None
cod_df: Optional[pd.DataFrame] = None
forecast_df: Optional[pd.DataFrame] = None
metadata: Optional[dict] = None
models: Optional[dict] = None


def _read_csv_safe(path: Path) -> pd.DataFrame:
	if path is None:
		return pd.DataFrame()
	try:
		if not Path(path).exists():
			return pd.DataFrame()
		return pd.read_csv(path)
	except Exception:
		return pd.DataFrame()


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
	"""Normalize column names to deterministic, backward-compatible keys.

	- Lowercase, strip whitespace and replace spaces with underscores.
	- Canonicalize known variants (e.g. `cod_policy_action` -> `cod_action`).
	This is intentionally conservative: we only rename to provide stable
	consumers keys; we do NOT drop or compute columns.
	"""
	if df is None or df.empty:
		return df

	df = df.copy()
	col_map = {}
	for c in df.columns:
		norm = str(c).strip().lower().replace(" ", "_")
		col_map[c] = norm

	df.columns = [col_map[c] for c in df.columns]

	# Backward compatibility mappings
	rename_map = {}

	# COD artifact variants -> canonical `cod_action`
	for candidate in ("cod_policy_action", "cod_action", "policy_action"):
		if candidate in df.columns:
			rename_map[candidate] = "cod_action"

	# Forecast probabilistic quantiles: tolerate variants like p_10, p10, P10
	for target, variants in {
		"p10": ("p10", "p_10", "p_10_forecast", "p10_forecast"),
		"p50": ("p50", "p_50", "p_50_forecast", "p50_forecast"),
		"p90": ("p90", "p_90", "p_90_forecast", "p90_forecast"),
	}.items():
		for v in variants:
			if v in df.columns and target not in df.columns:
				rename_map[v] = target

	# Reorder artifact common names
	for candidate in ("safety_stock", "safety_stock_qty"):
		if candidate in df.columns and "safety_stock" not in df.columns:
			rename_map[candidate] = "safety_stock"
	for candidate in ("reorder_point", "reorder_level"):
		if candidate in df.columns and "reorder_point" not in df.columns:
			rename_map[candidate] = "reorder_point"
	for candidate in ("moq", "min_order_qty", "minimum_order_quantity"):
		if candidate in df.columns and "moq" not in df.columns:
			rename_map[candidate] = "moq"

	if rename_map:
		# Only rename when necessary to avoid surprising consumers
		df = df.rename(columns=rename_map)

	return df


def load_artifacts(artifacts_dir: Optional[str | Path] = None) -> dict:
	"""Load canonical CSV artifacts into module-level variables.

	This is the authoritative loader for the HTTP server startup. It must be
	idempotent and fast; callers (startup event) may invoke it repeatedly.

	Behavior:
	- Reads only the three canonical artifact files (see README). No
	  computation or joins are performed here.
	- Normalizes column names for backward compatibility.
	- Populates `forecast_df`, `reorder_df`, `cod_df` and `metadata`.
	"""
	global reorder_df, cod_df, forecast_df, metadata

	base = Path(artifacts_dir) if artifacts_dir is not None else Path(os.getenv("ARTIFACTS_DIR", "artifacts"))

	# Filenames are authoritative; prefer the exact names produced offline.
	forecast_path = base / "weekly_forecast_future_all_skus.csv"
	reorder_path = base / "reorder_recommendations.csv"
	cod_path = base / "cod_intelligence.csv"

	forecast_df = _read_csv_safe(forecast_path)
	reorder_df = _read_csv_safe(reorder_path)
	cod_df = _read_csv_safe(cod_path)

	# Apply conservative column normalization for stable API keys
	forecast_df = _normalize_column_names(forecast_df)
	reorder_df = _normalize_column_names(reorder_df)
	cod_df = _normalize_column_names(cod_df)

	metadata = {
		"forecast_rows": 0 if forecast_df is None else len(forecast_df),
		"reorder_rows": 0 if reorder_df is None else len(reorder_df),
		"cod_rows": 0 if cod_df is None else len(cod_df),
		"artifacts_dir": str(base),
	}

	return metadata


def get_metadata() -> dict:
	return metadata or {}
