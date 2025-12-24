from pydantic import BaseModel
from typing import Optional, Literal


class ReorderRecommendation(BaseModel):
    sku_id: str
    warehouse_id: str
    demand_source: Optional[str]
    inventory_position: Optional[float]
    expected_demand_LT: Optional[float]
    safety_stock: Optional[float]
    reorder_point: Optional[float]
    reorder_required: Optional[bool]
    recommended_order_qty: Optional[int]
    sku_status: Optional[str]
    decision_reason: Optional[str]


class CODDecision(BaseModel):
    sku_id: str
    lane: Optional[str]
    historical_rto_rate: Optional[float]
    cod_share: Optional[float]
    cod_risk: Optional[str]
    cod_action: Optional[str]
    notes: Optional[str]


class ForecastRow(BaseModel):
    sku_id: str
    # allow arbitrary additional fields; typical columns include week and p10/p50/p90
    # clients should accept whatever CSV headers are present
    # We keep a minimal required field and allow dynamic rows returned as dicts
    pass
