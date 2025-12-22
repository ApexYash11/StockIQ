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

**Architecture Diagram**
The diagram below shows the flow from config -> generation -> outputs -> audit/fix. Renderable as Mermaid (use a Mermaid renderer or VS Code Mermaid preview).

```mermaid
flowchart TD
  subgraph cfg[Configuration]
    Cfg["config/world_config.json\ncampaigns, skus, seeds"]
  end
  subgraph gen[Generation]
    GO[Generate/generate_orders.py]
    GV[Generate/generate_vendors.py]
    GI[Generate/generate_inventory.py]
  end
  subgraph post[Post-process]
    AC[Generate/apply_campaigns.py]\n(augment orders deterministically)
    FD[Generate/fix_data.py]\n(dedup & regenerate inventory events)
  end
  subgraph out[Outputs]
    O[output/orders.csv]
    IE[output/inventory_events.csv]
    V[output/vendors.csv]
    CAM[output/campaigns.csv]
  end
  subgraph audit[Validation]
    AUD[Generate/audit_data.py]\n(structural + logic checks)
  end

  Cfg --> GO
  GO --> O
  GV --> V
  O --> GI
  V --> GI
  GI --> IE
  O --> AC
  AC --> O
  O --> FD
  V --> FD
  FD --> IE
  O --> AUD
  IE --> AUD
  V --> AUD
  CAM -.-> AC

  style cfg fill:#f9f,stroke:#333,stroke-width:1px
  style gen fill:#cff,stroke:#333,stroke-width:1px
  style post fill:#fcf,stroke:#333,stroke-width:1px
  style out fill:#cfc,stroke:#333,stroke-width:1px
  style audit fill:#ffc,stroke:#333,stroke-width:1px
```

**Developer notes & provenance**
- All scripts are intentionally small, deterministic, and documented inline; please inspect `Generate/` for implementation details and comments.
- This README is intended to be exact and actionable for demo runs and experimentation.

