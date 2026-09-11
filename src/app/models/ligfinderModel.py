from typing import List, Optional, Any
from pydantic import BaseModel


class CriteriaItem(BaseModel):
    type: str
    column: List[Any]
    value: str


class CriteriaObject(BaseModel):
    status: str
    data: dict


class MetricCriteria(BaseModel):
    column: str
    operation: str
    value: str

class GRZCriteria(BaseModel):
    column: str
    operation: str
    value: str

class TableRequest(BaseModel):
    geometry: Optional[List[Any]]
    criteria: Optional[List[CriteriaObject]]
    metric: Optional[List[MetricCriteria]]
    grz : Optional[List[GRZCriteria]]
    table_name: Optional[str] = "parcel_grz_29042025"

class MaximizerRequest(BaseModel):
    geometry: Optional[List[Any]]
    criteria: Optional[List[CriteriaObject]]
    metric: Optional[List[MetricCriteria]]
    grz : Optional[List[GRZCriteria]]
    table_name: Optional[str] = "parcel_grz_29042025"
    threshold: Optional[float] = 0.0
