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

class CriteriaGroup(BaseModel):
    data: dict
    status: str

class Group(BaseModel):
    inner_operator: Optional[str] = "OR"
    criteria: List[CriteriaGroup]

class TableRequest(BaseModel):
    geometry: Optional[List[Any]] = None
    criteria: Optional[List[CriteriaObject]] = None
    groups: Optional[List[Group]] = None
    between_groups_operator: Optional[str] = "AND"
    metric: Optional[List[MetricCriteria]] = None
    grz: Optional[List[GRZCriteria]] = None
    table_name: Optional[str] = "parcel_grz_29042025"

class MaximizerRequest(BaseModel):
    geometry: Optional[List[Any]] = None
    criteria: Optional[List[CriteriaObject]] = None
    groups: Optional[List[Group]] = None
    between_groups_operator: Optional[str] = "AND"
    metric: Optional[List[MetricCriteria]] = None
    grz: Optional[List[GRZCriteria]] = None
    table_name: Optional[str] = "parcel_grz_29042025"
    threshold: Optional[float] = 0.0
