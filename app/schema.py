from pydantic import BaseModel
from typing import Optional ,Literal

class ReorderRecommendation(BaseModel):
  sku_id: str
  warehouse_id: str
  inventory_position: int
  reorder_point: int
  recoommded_order_qty: int
  cod_risk: Literal["Low", "Medium", "High"]
  cod_action : Literal["Allow COD", "Disallow COD","limit COD"]


class CODDecision(BaseModel):
  sku_id: str
  lane: str
  cod_action : Literal["Allow COD", "Disallow COD","limit COD"]
  cod_risk: Literal["Low", "Medium", "High"]
  explaination: Optional[str] = None
