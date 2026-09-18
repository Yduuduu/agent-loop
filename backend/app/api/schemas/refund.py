from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class RefundRequestCreateResponse(BaseModel):
    case_id: str


class RefundCaseStatusResponse(BaseModel):
    case_id: str
    order_id: str
    status: Literal["pending", "in_progress", "awaiting_human", "completed", "failed"]
    requires_human: bool
    decision: Literal["approve", "reject", "needs_human", "resolved"] | None
    decision_reason: str | None
    flagged_reason: str | None
    refund_amount: float | None
    awaiting_human_since: datetime | None
    created_at: datetime
    updated_at: datetime


class ResumeAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    TAKEOVER = "takeover"


class RefundResumeRequest(BaseModel):
    """POST /api/refund-requests/{case_id}/resume 페이로드 계약.

    approve/reject는 admin_note(내부 사유)를 쓰고, takeover(관리자 직접 개입)는
    admin_message(고객에게 남기는 처리 결과)를 최종 decision_reason으로 그대로 쓴다.
    """

    action: ResumeAction
    admin_note: str | None = None
    admin_message: str | None = None
