"""对话替换的边界模型。预览只提供候选，确认时只接受服务端候选 ID。"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .schemas import TripPlan


class EditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["ask", "replace", "clarify"]
    reply: str = Field(default="", max_length=2000)
    day_number: Optional[int] = Field(default=None, ge=1, le=30)
    attraction_number: Optional[int] = Field(default=None, ge=1, le=100)
    attraction_name: Optional[str] = Field(default=None, max_length=150)
    search_query: str = Field(default="景点", max_length=80)
    district: Optional[str] = Field(default=None, max_length=40)
    indoor_only: bool = False
    max_ticket_price: Optional[float] = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    unsupported_constraints: list[str] = Field(default_factory=list, max_length=5)


class TripEditApplyRequest(BaseModel):
    proposal_id: str = Field(min_length=16, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=120)
    trip_plan: TripPlan
    language: Literal["zh", "en", "ja"] = "zh"
