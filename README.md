# StockIQ

## Executive summary
StockIQ is a production-oriented Inventory, Forecasting, and Decision Intelligence system for direct-to-consumer (D2C) operations. It converts raw order and inventory events into probabilistic weekly demand forecasts (P10 / P50 / P90), routes SKUs to appropriate forecasting strategies, allocates demand across warehouses, and emits MOQ-aware, uncertainty-informed reorder recommendations ready for API serving and operational review.

## System overview
- Input: `orders.csv`, `inventory_events.csv`, `vendors.csv`, `campaigns.csv`.
- Data preparation: calendar-safe weekly aggregation and campaign-intensity features.
- Routing: deterministic per-SKU routing to `PRIMARY_SARIMAX`, `FALLBACK_HISTORY`, or `FALLBACK_NAIVE` based on history length.
- Forecasting: SARIMAX per-SKU where sufficient history exists; outputs P50 and predictive intervals used to derive P10/P90.
- Allocation: SKU totals are allocated to warehouses using historical shares with a minimum-share floor and renormalization.
- Decisioning: warehouse-level reorder points computed as allocated expected demand (lead time) + allocated safety stock; recommended orders respect `MOQ`.
- Artifacts: JSON-ready `decision_df` and audit CSVs (e.g., `sku_demand_allocation_debug.csv`) for monitoring and senior review.

## High-level architecture
```mermaid
flowchart LR
  A[Raw Data: orders, inventory, vendors, campaigns] --> B[ETL & Weekly Aggregation]
  B --> C[SKU Routing]
  C --> D[Demand Forecasting (SARIMAX or fallback)]
  D --> E[Forecast Outputs (P10/P50/P90)]
  E --> F[Warehouse Demand Allocation (historical shares + MIN_SHARE)]
  F --> G[Reorder Engine (MOQ-aware, safety stock)]
  G --> H[Decisions (JSON) & Audit Artifacts (CSV)]
  A --> I[COD Intelligence]
  I --> H
  H --> J[API Layer (FastAPI) / Monitoring / Dashboards]
```

## Core components

### Demand Forecasting
- Per-SKU SARIMAX where history supports seasonality (s=52 weekly).
- Produces predictive mean and intervals; P10/P90 come from model predictive intervals (or bootstrap for non-Gaussian cases).
- Probabilistic forecasts enable safety-stock calculations and risk-aware ordering.

### SKU Routing
- Deterministic thresholds route SKUs to either SARIMAX (`PRIMARY_SARIMAX`) or fallbacks (`FALLBACK_HISTORY`, `FALLBACK_NAIVE`).
- Routing preserves stability and observability: each decision records `demand_source`.

### Inventory & Reorder Engine
- Warehouse allocation computed from historical outbound shares; fallback to inventory distribution or equal split.
- Enforces a `MIN_SHARE` floor per active warehouse to avoid zero-exposure and renormalizes shares so SKU totals are preserved.
- Warehouse-level reorder point = allocated expected demand (lead time) + allocated safety stock.
- Recommended order quantity is rounded up to nearest `MOQ` when `inventory_position` ≤ `reorder_point`.
- Outputs are JSON-serializable and include audit fields for traceability.

### COD Intelligence
- Aggregates order-level COD behaviour and RTO rates per (sku, region/warehouse).
- Produces RTO risk buckets and policy actions (ALLOW / LIMIT / DISABLE) to drive business rules.

## Decision flow example (one SKU)
1. Weekly aggregation yields a weekly time-series and `campaign_intensity`.
2. SKU routing picks SARIMAX for a mature SKU.
3. SARIMAX produces P50 and an 80% interval → P10/P90.
4. Sum P50 across lead-time → SKU expected demand; sum P90−P50 → SKU safety stock.
5. Compute warehouse shares from historical outbound ratios; apply MIN_SHARE floor and renormalize.
6. Allocate SKU totals to warehouses by share and compute warehouse reorder points.
7. If `inventory_position` ≤ reorder point, recommend order quantity rounded to `MOQ`.

## Tech stack
- Python 3.x, pandas, numpy
- statsmodels (SARIMAX)
- FastAPI-ready JSON outputs
- Jupyter / Streamlit for experimentation and dashboards

## Why production-ready
- Deterministic routing and guardrails prevent silent failures.
- Forecasts and artifacts are versionable and serializable (`SARIMAXResults.save()`).
- Fallback hierarchy prevents crashes on sparse data and is logged for observability.
- Outputs are JSON-serializable, schema-friendly, and designed for FastAPI endpoints.

## Monitoring & diagnostics
- `sku_demand_allocation_debug.csv` – per-SKU allocated expected and safety sums for validation.
- Counts of SKUs per strategy, fraction of fallbacks, calibration of P10–P90 coverage should be monitored.

## Future extensions
- Batch inference service + scheduled re-runs with drift alerts.
- FastAPI wrapper and request/response JSON schema with auth and request validation.
- Optimization layer for cost-aware, consolidated purchase orders and cross-warehouse fulfillment.
- Quantile ML models for sparse SKUs and hierarchical models to borrow strength across SKUs.

## Skills demonstrated
- Time-series forecasting and uncertainty quantification
- Production-safe routing & fallback design for sparse data
- Multi-warehouse demand allocation with risk floors and renormalization
- Operationally aware reorder algorithms (MOQ, lead time, safety stock)
- Observability and artifact design for audit and monitoring

## Repo layout (quick)
- `/notebooks` — experiments: forecasting, SKU mapping, COD intelligence
- `/scripts` — small utilities and validators
- `/Generate` — synthetic data generators
- `/output` — generated CSV inputs
- `/artifacts` — debug CSVs and serialized models

If you want, I can add a concise FastAPI wrapper that returns `decision_df` as JSON with request validation and an optional debug flag. 
**StockIQ — Synthetic Demand & Inventory Demo**

This repository builds a reproducible synthetic dataset for a demo of demand, campaigns, vendors, and event-sourced inventory suitable for analytics and ML experiments.

**Quick Summary**:
- **Purpose**: produce internally-consistent, ML-ready CSVs (`orders.csv`, `inventory_events.csv`, `vendors.csv`, `campaigns.csv`) with deterministic randomness so experiments are reproducible.
- **Language / libs**: Python 3, pandas, numpy.
- **Location of code**: `Generate/` contains all generation and post-processing scripts.

**Files (top-level)**
- `requirements.txt`: Python dependencies.
- `config/world_config.json`: campaign & SKU tuning (source of truth for campaign parameters).
- `output/`: destination for generated CSVs.
- `Generate/`: scripts to generate, fix, apply campaigns, and audit.

**Key CSV outputs (ML-ready)**
- `output/orders.csv` — transactional orders. Columns include `order_id`, `order_date` (day offset), `sku_id`, `region`, `payment_type`, `delivery_days`, `delivery_status`, `campaign_applied`, `order_quantity`.
- `output/inventory_events.csv` — event-sourced inventory stream. Event types: `INITIAL_STOCK`, `OUTBOUND`, `REPLENISHMENT_INBOUND`.
- `output/vendors.csv` — vendor per SKU with `lead_time_days`, `MOQ`, `unit_cost`.
- `output/campaigns.csv` — campaign definitions (seeded from config).

**Primary Scripts**
- `Generate/generate_orders.py` — generate baseline orders (uses config/world_config.json). See: [Generate/generate_orders.py](Generate/generate_orders.py)
- `Generate/generate_vendors.py` — produce `vendors.csv` (one vendor per SKU). See: [Generate/generate_vendors.py](Generate/generate_vendors.py)
- `Generate/generate_inventory.py` — produce event-sourced `inventory_events.csv` from orders + vendors. See: [Generate/generate_inventory.py](Generate/generate_inventory.py)
- `Generate/apply_campaigns.py` — deterministic post-process that injects campaign-driven demand into `orders.csv` and validates uplift. See: [Generate/apply_campaigns.py](Generate/apply_campaigns.py)
- `Generate/fix_data.py` — deduplicate and regenerate event streams; used to collapse exact order duplicates and ensure no permanent negative stock. See: [Generate/fix_data.py](Generate/fix_data.py)
- `Generate/audit_data.py` — runs structural and cross-file validations and reports issues. See: [Generate/audit_data.py](Generate/audit_data.py)

**How to run (recommended workflow)**
1. Create & activate virtualenv, install deps:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1    # PowerShell
pip install -r requirements.txt
```

2. Generate baseline data (order of commands matters):

```powershell
venv\Scripts\python.exe Generate\generate_orders.py
venv\Scripts\python.exe Generate\generate_vendors.py
venv\Scripts\python.exe Generate\generate_inventory.py
```

3. (Optional) Apply campaign uplift deterministically:

```powershell
venv\Scripts\python.exe Generate\apply_campaigns.py
```

4. If data has issues, run fix script:

```powershell
venv\Scripts\python.exe Generate\fix_data.py
```

5. Run the audit to validate everything:

```powershell
venv\Scripts\python.exe Generate\audit_data.py
```

**How campaigns are made detectable (design notes)**
- Deterministic uplift: `Generate/apply_campaigns.py` enforces a minimum uplift (configurable constant `MIN_UPLIFT`) so campaign signal is detectable in downstream audits and ML validations without adding noise.
- Focused uplift: injected orders preferentially use the top fraction of SKUs by historical volume (`TOP_SKU_FRAC`) to reflect realistic promotional concentration.
- No duplicates: injected rows receive deterministic `order_id` values prefixed with `CAM_...` and the script guarantees no `order_id` collisions with existing orders.
- Reproducibility: script uses a fixed RNG seed and deterministic id generation.

**Validation & Safety**
- `apply_campaigns.py` performs a post-check asserting mean orders/day DURING campaign windows exceeds OUTSIDE by a configurable multiplier `MIN_MEAN_MULT`.
- `fix_data.py` regenerates `inventory_events.csv` and asserts final stock is non-negative for all `(warehouse,sku)` pairs.
- `audit_data.py` performs structural checks, cross-file consistency, inventory event type checks, and RTO sanity checks.

**Tuning tips**
- To strengthen campaigns, edit `config/world_config.json` to increase `uplift` per campaign or change campaign `start_day`/`duration_days`.
- To concentrate uplift more, adjust `TOP_SKU_FRAC` inside `Generate/apply_campaigns.py` (lower means narrower SKU focus).
- To make smaller changes, lower `MIN_UPLIFT` or adjust `MIN_MEAN_MULT` threshold in the script.
# StockIQ — Detailed repository guide

This README is a reviewer-oriented, production-ready description of the StockIQ project. It explains the system purpose, per-file responsibilities, operational assumptions, run instructions, and recommended next steps for production hardening.

## Executive summary
StockIQ is an end-to-end Inventory, Forecasting, and Decision Intelligence system for D2C operations. It: 

- Produces weekly probabilistic demand forecasts (P10 / P50 / P90) for SKUs where sufficient history exists.
- Routes SKUs to the best available strategy (SARIMAX primary, history fallback, naive fallback).
- Allocates SKU demand across warehouses using historical shares with a configurable minimum-share floor and renormalization.
- Emits MOQ-aware reorder recommendations per warehouse and writes audit artifacts for monitoring and validation.

Goal: provide deterministic, auditable decisions suitable for wrapping behind a FastAPI service while demonstrating strong ML, data-engineering, and product thinking.

---

## Table of contents
1. Project layout (file-by-file)
2. End-to-end flow (diagram)
3. How to run (developer runbook)
4. Core components (technical detail)
5. Operational checks & diagnostics
6. Recommendations & next steps

---

## 1) Project layout (file-by-file)
Top-level files and directories with their responsibilities (accurate to repository state):

- `README.md` — this file.
- `requirements.txt` — Python dependencies used by notebooks and scripts.

- `config/world_config.json` — environment/config defaults used by notebooks (region mappings, constants).

- `Generate/` — development helpers and synthetic-data generators. Useful for reproducible local testing.
  - `generate_orders.py` — synthetic orders generator.
  - `generate_inventory.py` — generate inventory event streams.
  - `generate_vendors.py` — create vendor lead-times and MOQ data.
  - `generate_campaigns.py`, `apply_campaigns.py` — produce and apply campaign/exogenous signals.
  - `fix_data.py` — cleaning helpers for generated CSVs.
  - `audit_data.py` — data checks and asserts.

- `notebooks/` — runnable, linear pipelines and analysis (recommended extraction into modules for production):
  - `forecasting_v2.ipynb` — weekly aggregation, SARIMAX model workflow (fit, validation, future forecast), and evaluation metrics.
  - `sku_mapping_and_reorder_engine.ipynb` — SKU routing, warehouse allocation (historical → inventory → equal), MIN_SHARE floor enforcement, allocation, MOQ-aware reorder logic, and audit artifact generation.
  - `cod_intelligence.ipynb` — COD / RTO analysis and policy artifact generation.
  - `notebooks/models/` — saved model pickles (example SARIMAXResults).

- `output/` — input CSVs used by notebooks (canonical inputs for runs):
  - `orders.csv`, `inventory_events.csv`, `vendors.csv`, `campaigns.csv`.

- `artifacts/` — generated audit outputs and serialized models.
  - `sku_demand_allocation_debug.csv` — SKU-level allocated sums (monitoring artifact).
  - `cod_intelligence.csv` — COD policy artifact.

- `scripts/` — small utilities for CI and operations:
  - `conunt.py` — SKU coverage audit (auto-detect SKU columns and report counts).
  - `dyamic_engine.py` — experimental runner.

---

## 2) End-to-end flow (diagram)
```mermaid
flowchart LR
  A[Raw CSVs: orders, inventory, vendors, campaigns] --> B[ETL & Weekly Aggregation]
  B --> C[SKU Routing (thresholds)]
  C --> D[Forecasting: SARIMAX or fallback]
  D --> E[Forecast outputs: P10 / P50 / P90]
  E --> F[Warehouse allocation: history -> inventory -> equal; MIN_SHARE enforced]
  F --> G[Reorder engine (reorder_point = allocated_expected + allocated_safety)]
  G --> H[Decision outputs (JSON) + Artifacts (CSV)]
  A --> I[COD Intelligence]
  I --> H
  H --> J[Serving Layer (FastAPI) / Monitoring]
```

Notes: the pipeline is intentionally modular to allow extraction of each stage (forecasting, allocation, decisioning) to separate services.

---

## 3) How to run (developer runbook)
Minimal sequence to reproduce artifacts locally.

1. Create & activate environment

   python -m venv .venv
   .\.venv\Scripts\activate

2. Install dependencies

   pip install -r requirements.txt

3. (Optional) Generate sample data

   python Generate/generate_vendors.py
   python Generate/generate_inventory.py
   python Generate/generate_orders.py
   python Generate/generate_campaigns.py
   python Generate/apply_campaigns.py

4. Run forecasting pipeline

   - Open `notebooks/forecasting_v2.ipynb` and run cells in order (or extract the notebook code into a script for reproducible runs).

5. Run reorder engine

   - Open `notebooks/sku_mapping_and_reorder_engine.ipynb` and run cells in order. This writes `artifacts/sku_demand_allocation_debug.csv` and produces `decision_df`.

6. Quick checks

   python scripts/conunt.py  # SKU coverage audit

Notes on converting to production:
- Extract core engine functions and represent them as deterministic Python functions (no global notebook state). Add unit tests and package the result as `stockiq.engine`.
- Add a FastAPI wrapper around a function that returns `decision_df.to_dict(orient='records')`.

---

## 4) Core components (technical detail)

Demand forecasting
- Approach: per-SKU SARIMAX when enough weekly history exists. Seasonality baseline uses s=52 for weekly data.
- Outputs: `p50` (predicted mean) and prediction intervals. P10/P90 derived from model intervals for safety-stock computations.

SKU routing and fallbacks
- `route_sku()` uses deterministic thresholds to choose between `PRIMARY_SARIMAX`, `FALLBACK_HISTORY`, `FALLBACK_NAIVE`.
- All outputs include `demand_source` to make strategy usage auditable.

Warehouse allocation
- Preference order:
  1. Historical outbound orders per `(sku_id, warehouse)`
  2. Inventory snapshot distribution per `(sku_id, warehouse)`
  3. Equal split across active warehouses
- Enforce `MIN_SHARE` (configurable; default 0.05) per active warehouse, renormalize so shares sum to 1.0. Business rationale: avoid zero-exposure warehouses and make allocation robust to reporting gaps.

Reorder engine
- `reorder_point = allocated_expected + allocated_safety`
- `recommended_order_qty` is rounded up to the nearest `MOQ` when `inventory_position` ≤ `reorder_point`.
- All numeric outputs are coerced to safe numeric types with NaNs replaced by 0.0 for JSON serialization.

COD intelligence
- Aggregates COD share and RTO rate per `(sku_id, region)` and maps to `warehouse_id`. Produces risk buckets and policy actions used by operations.

---

## 5) Operational checks & diagnostics
Artifacts and checks to run as part of validation or CI:

- `scripts/conunt.py`: confirm input CSVs exist and report SKU counts.
- `artifacts/sku_demand_allocation_debug.csv`: validate that per-SKU `allocated_expected_sum` ≈ SKU-level expected totals (tolerance for fallbacks).
- Notebook sanity checks: ensure `decision_df` has no NaNs in required numeric columns and `recommended_order_qty` is non-negative integer.

Suggested CI steps:
- `python scripts/conunt.py` (fail on missing inputs)
- Unit tests for `MIN_SHARE` enforcement and renormalization.

---

## 6) Recommendations & next steps
Short roadmap to production readiness:

1. Extract engine into a small package (e.g., `stockiq.engine`) and add unit tests.
2. Add a minimal FastAPI wrapper that exposes a `POST /decisions` endpoint returning `decision_df` as JSON and an optional debug flag to write artifacts.
3. Add CI checks and a lightweight integration test that runs the pipeline against synthetic data from `Generate/` and asserts diagnostic invariants.
4. Add proper environment/config management (separate `config` for prod vs dev) and model metadata persistence (training date, transforms used).

---

If you want, I will now:

1) implement a one-file FastAPI wrapper to serve `decision_df` (with debug flag), or
2) extract the engine code into a proper module and add unit tests for allocation and no-NaN guarantees.

Reply with `1` or `2` (or both) and I will implement the chosen step next.

