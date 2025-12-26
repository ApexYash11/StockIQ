from pydantic import BaseModel
from typing import Optional, Literal

# Schema definitions for various data models
# Reorder Recommendation Schema
class ReorderRecommendation(BaseModel):
    sku_id: str
    warehouse_id: str
    demand_source: Optional[str]
    inventory_position: Optional[float]
    expected_demand_LT: Optional[float]
    safety_stock: Optional[float]
    reorder_point: Optional[float]
    reorder_required: Optional[bool]
    recommended_order_qty: Optional[float]
    sku_status: Optional[str]
    decision_reason: Optional[str]

# COD Decision Schema
class CODDecision(BaseModel):
    sku_id: str
    lane: Optional[str]
    historical_rto_rate: Optional[float]
    cod_share: Optional[float]
    cod_risk: Optional[str]
    cod_action: Optional[str]
    notes: Optional[str]


# Forecast Row Schema
class ForecastRow(BaseModel):
    sku_id: str
    pass
