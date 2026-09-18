from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RefundRequestCreateResponse(BaseModel):
    case_id: str


class RefundCaseStatusResponse(BaseModel):
    case_id: str
    order_id: str
    status: Literal["pending", "in_progress", "awaiting_human", "completed", "failed"]
    requires_human: bool
    decision: Literal["approve", "reject", "needs_human"] | None
    decision_reason: str | None
    flagged_reason: str | None
    awaiting_human_since: datetime | None
    created_at: datetime
    updated_at: datetime
