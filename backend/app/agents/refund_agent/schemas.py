from typing import Literal

from pydantic import BaseModel, Field


class DamageAssessment(BaseModel):
    """damage_assessment 노드의 구조화 출력."""

    is_damaged: bool
    severity: Literal["none", "minor", "moderate", "severe"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class Decision(BaseModel):
    """decision 노드의 구조화 출력."""

    decision: Literal["approve", "reject", "needs_human"]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
