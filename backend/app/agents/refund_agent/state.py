"""RefundAgent 그래프 상태 스키마.

이 TypedDict는 Phase 2 SSE 이벤트와 Phase 4 프론트 상태가 그대로 참조하는
고정 계약이다. 필드를 바꾸면 두 Phase의 매핑도 함께 갱신해야 한다.
"""

import operator
from typing import Annotated, Literal, TypedDict


class TraceEntry(TypedDict):
    node: str
    event: Literal["start", "end"]
    detail: str


class RefundAgentState(TypedDict):
    # 입력
    order_id: str
    user_message: str
    image_refs: list[str]

    # 중간 산출물 (노드가 한 번씩 채워 넣음 — 덮어쓰기)
    order_data: dict | None
    damage_assessment: dict | None
    policy_findings: list[dict]

    # 최종 산출물 (덮어쓰기)
    decision: Literal["approve", "reject", "needs_human"] | None
    decision_reason: str | None
    requires_human: bool

    # 관측/표시용 — 노드마다 누적(operator.add)되는 리스트이므로
    # 각 노드는 전체 리스트가 아니라 새로 추가할 항목만 반환해야 한다.
    messages: Annotated[list[str], operator.add]
    trace: Annotated[list[TraceEntry], operator.add]


def initial_state(*, order_id: str, user_message: str, image_refs: list[str]) -> RefundAgentState:
    return RefundAgentState(
        order_id=order_id,
        user_message=user_message,
        image_refs=image_refs,
        order_data=None,
        damage_assessment=None,
        policy_findings=[],
        decision=None,
        decision_reason=None,
        requires_human=False,
        messages=[],
        trace=[],
    )
