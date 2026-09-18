"""RefundAgent 그래프를 실행하며 진행 상황을 SSE 이벤트로 발행하고
최종 결과를 DB에 반영한다.

노드 단위 세분화는 Phase 1에서 이미 결정된 대로다: order_lookup/policy_rag_search는
"tool_call"로, damage_assessment/decision은 "node_end"로 노출한다. 그래프의 다음
노드는 고정 엣지(STATIC_NEXT)와, decision 이후에는 Phase 1이 노출한
route_after_decision()을 그대로 재사용해 판단한다 — LangGraph 내부 이벤트에
의존하지 않고 이 모듈이 직접 어댑터 역할을 한다.
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import select

from app.agents.refund_agent.nodes import route_after_decision
from app.agents.refund_agent.state import RefundAgentState
from app.api import event_bus
from app.api.deps import GraphBuilder
from app.api.schemas.sse_events import SSEEvent, SSEEventType
from app.db.models import RefundCase, RefundDecision
from app.db.session import async_session_factory

STATIC_NEXT: dict[str, str] = {
    "order_lookup": "damage_assessment",
    "damage_assessment": "policy_rag_search",
    "policy_rag_search": "decision",
}

TOOL_CALL_NODES = {"order_lookup", "policy_rag_search"}
TERMINAL_NODES = {"finalize", "flag_for_human"}


async def run_case(case_id: str, build_graph: GraphBuilder, state: RefundAgentState) -> None:
    async with async_session_factory() as session:
        case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
        assert case is not None
        case.status = "in_progress"
        await session.commit()

    graph = build_graph()
    state_acc: dict = dict(state)

    try:
        await event_bus.publish(
            case_id,
            SSEEvent(event=SSEEventType.NODE_START, case_id=case_id, data={"node": "order_lookup"}),
        )

        async for step in graph.astream(state, stream_mode="updates"):
            for node_name, update in step.items():
                state_acc.update(
                    {k: v for k, v in update.items() if k not in ("messages", "trace")}
                )
                summary = update.get("messages", [""])[0] if update.get("messages") else ""

                if node_name in TOOL_CALL_NODES:
                    await event_bus.publish(
                        case_id,
                        SSEEvent(
                            event=SSEEventType.TOOL_CALL,
                            case_id=case_id,
                            data={"node": node_name, "summary": summary},
                        ),
                    )
                elif node_name in TERMINAL_NODES:
                    await event_bus.publish(
                        case_id,
                        SSEEvent(
                            event=SSEEventType.DECISION,
                            case_id=case_id,
                            data={
                                "decision": state_acc.get("decision"),
                                "reason": state_acc.get("decision_reason"),
                                "requires_human": state_acc.get("requires_human"),
                            },
                        ),
                    )
                else:
                    await event_bus.publish(
                        case_id,
                        SSEEvent(
                            event=SSEEventType.NODE_END,
                            case_id=case_id,
                            data={"node": node_name, "summary": summary},
                        ),
                    )

                next_node = _next_node(node_name, state_acc)
                if next_node is not None:
                    await event_bus.publish(
                        case_id,
                        SSEEvent(
                            event=SSEEventType.NODE_START, case_id=case_id, data={"node": next_node}
                        ),
                    )

        await _persist_result(case_id, state_acc)
    except Exception as exc:  # noqa: BLE001 — 원인 불문 error 이벤트로 알리고 case를 failed 처리
        await event_bus.publish(
            case_id, SSEEvent(event=SSEEventType.ERROR, case_id=case_id, data={"message": str(exc)})
        )
        await _persist_failure(case_id)
    finally:
        await event_bus.publish_done(case_id)


def _next_node(completed_node: str, state_acc: dict) -> str | None:
    if completed_node in TERMINAL_NODES:
        return None
    if completed_node == "decision":
        return route_after_decision(state_acc)  # type: ignore[arg-type]
    return STATIC_NEXT.get(completed_node)


async def _persist_result(case_id: str, state_acc: dict) -> None:
    status: Literal["completed", "awaiting_human"] = (
        "awaiting_human" if state_acc.get("requires_human") else "completed"
    )

    async with async_session_factory() as session:
        case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
        assert case is not None
        case.status = status
        if status == "awaiting_human":
            case.flagged_reason = state_acc.get("decision_reason")
            case.awaiting_human_since = datetime.utcnow()

        session.add(
            RefundDecision(
                case_id=case_id,
                decision=state_acc.get("decision") or "needs_human",
                reason=state_acc.get("decision_reason") or "",
                requires_human=bool(state_acc.get("requires_human")),
            )
        )
        await session.commit()


async def _persist_failure(case_id: str) -> None:
    async with async_session_factory() as session:
        case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
        assert case is not None
        case.status = "failed"
        await session.commit()
