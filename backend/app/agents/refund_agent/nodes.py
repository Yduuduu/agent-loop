"""RefundAgent 그래프 노드.

각 노드는 실제 구현(LLM 호출, DB 조회, RAG 검색)을 기본값으로 갖되,
`Callable` 의존성을 주입받을 수 있어 테스트에서는 결정론적인 fake로
치환한다(app/agents/refund_agent/graph.py의 build_graph 참고).
"""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Literal

from langchain_openai import ChatOpenAI

from app.agents.refund_agent.prompts import (
    DAMAGE_ASSESSMENT_SYSTEM_PROMPT,
    DAMAGE_ASSESSMENT_USER_TEMPLATE,
    DECISION_SYSTEM_PROMPT,
    DECISION_USER_TEMPLATE,
)
from app.agents.refund_agent.schemas import DamageAssessment, Decision
from app.agents.refund_agent.state import RefundAgentState
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.tools.order_lookup import lookup_order
from app.tools.policy_rag_search import search_policy

# 정책 문서(refund_policy.pdf) 3절 "고액 환불 승인 정책"과 동일한 기준.
HIGH_VALUE_THRESHOLD_USD = 500.0
LOW_CONFIDENCE_THRESHOLD = 0.6

AssessDamageFn = Callable[[str, list[str]], Awaitable[DamageAssessment]]
DecideFn = Callable[[dict, dict, list[dict], str], Awaitable[Decision]]
SearchPolicyFn = Callable[[str], Awaitable[list[dict]]]
OrderLookupFn = Callable[[str], Awaitable[dict | None]]
NowFn = Callable[[], date]


async def default_order_lookup(order_id: str) -> dict | None:
    async with async_session_factory() as session:
        return await lookup_order(session, order_id)


async def default_assess_damage(user_message: str, image_refs: list[str]) -> DamageAssessment:
    settings = get_settings()
    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=settings.openai_api_key)
    structured_llm = llm.with_structured_output(DamageAssessment)
    prompt = DAMAGE_ASSESSMENT_USER_TEMPLATE.format(
        user_message=user_message, image_refs=image_refs
    )
    result = await structured_llm.ainvoke(
        [
            {"role": "system", "content": DAMAGE_ASSESSMENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return result  # type: ignore[return-value]


async def default_search_policy(query: str) -> list[dict]:
    return await search_policy(query)


async def default_decide(
    order_data: dict, damage_assessment: dict, policy_findings: list[dict], reference_date: str
) -> Decision:
    settings = get_settings()
    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=settings.openai_api_key)
    structured_llm = llm.with_structured_output(Decision)
    prompt = DECISION_USER_TEMPLATE.format(
        reference_date=reference_date,
        order_data=order_data,
        damage_assessment=damage_assessment,
        policy_findings=policy_findings,
    )
    result = await structured_llm.ainvoke(
        [
            {"role": "system", "content": DECISION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return result  # type: ignore[return-value]


def make_order_lookup_node(order_lookup: OrderLookupFn = default_order_lookup):
    async def order_lookup_node(state: RefundAgentState) -> dict:
        order_data = await order_lookup(state["order_id"])
        if order_data is None:
            raise ValueError(f"주문을 찾을 수 없습니다: {state['order_id']}")
        return {
            "order_data": order_data,
            "messages": [
                f"주문 내역 조회 완료: {order_data['order_id']} ({len(order_data['items'])}개 품목)"
            ],
            "trace": [{"node": "order_lookup", "event": "end", "detail": order_data["order_id"]}],
        }

    return order_lookup_node


def make_damage_assessment_node(assess_damage: AssessDamageFn = default_assess_damage):
    async def damage_assessment_node(state: RefundAgentState) -> dict:
        assessment = await assess_damage(state["user_message"], state["image_refs"])
        return {
            "damage_assessment": assessment.model_dump(),
            "messages": [
                f"파손 판정 완료: is_damaged={assessment.is_damaged}, "
                f"severity={assessment.severity}, confidence={assessment.confidence:.2f}"
            ],
            "trace": [{"node": "damage_assessment", "event": "end", "detail": assessment.severity}],
        }

    return damage_assessment_node


def make_policy_rag_search_node(search: SearchPolicyFn = default_search_policy):
    async def policy_rag_search_node(state: RefundAgentState) -> dict:
        damage = state["damage_assessment"] or {}
        query = (
            f"{state['user_message']} "
            f"(파손 여부: {damage.get('is_damaged')}, 심각도: {damage.get('severity')})"
        )
        findings = await search(query)
        return {
            "policy_findings": findings,
            "messages": [f"관련 정책 조항 {len(findings)}건 검색 완료"],
            "trace": [
                {"node": "policy_rag_search", "event": "end", "detail": f"{len(findings)} chunks"}
            ],
        }

    return policy_rag_search_node


def make_decision_node(decide: DecideFn = default_decide, now_fn: NowFn = date.today):
    async def decision_node(state: RefundAgentState) -> dict:
        result = await decide(
            state["order_data"] or {},
            state["damage_assessment"] or {},
            state["policy_findings"],
            now_fn().isoformat(),
        )
        # LLM이 스스로 needs_human을 고르지 않았더라도 확신이 낮으면 사람 검토로 돌린다.
        requires_human = (
            result.decision == "needs_human" or result.confidence < LOW_CONFIDENCE_THRESHOLD
        )
        return {
            "decision": result.decision,
            "decision_reason": result.reason,
            "requires_human": requires_human,
            "messages": [
                f"1차 판정: {result.decision} "
                f"(confidence={result.confidence:.2f}) — {result.reason}"
            ],
            "trace": [
                {
                    "node": "decision",
                    "event": "end",
                    "detail": f"{result.decision}:{result.confidence:.2f}",
                }
            ],
        }

    return decision_node


def route_after_decision(state: RefundAgentState) -> Literal["finalize", "flag_for_human"]:
    order_data = state["order_data"] or {}
    if state["requires_human"] or order_data.get("total_amount", 0) > HIGH_VALUE_THRESHOLD_USD:
        return "flag_for_human"

    return "finalize"


async def finalize_node(state: RefundAgentState) -> dict:
    return {
        "requires_human": False,
        "messages": [f"최종 판정 완료: {state['decision']}"],
        "trace": [{"node": "finalize", "event": "end", "detail": state["decision"] or ""}],
    }


async def flag_for_human_node(state: RefundAgentState) -> dict:
    order_data = state["order_data"] or {}
    escalation_reason = state["decision_reason"] or ""
    if (
        state["decision"] != "needs_human"
        and order_data.get("total_amount", 0) > HIGH_VALUE_THRESHOLD_USD
    ):
        amount = order_data.get("total_amount", 0)
        escalation_reason = (
            f"환불 금액(${amount:.2f})이 고액 기준(${HIGH_VALUE_THRESHOLD_USD:.0f})을 초과해 "
            f"사람 검토가 필요합니다. (1차 판정: {state['decision']} — {escalation_reason})"
        )
    return {
        "decision": "needs_human",
        "decision_reason": escalation_reason,
        "requires_human": True,
        "messages": ["사람 검토 대기 상태로 전환됨"],
        "trace": [{"node": "flag_for_human", "event": "end", "detail": "awaiting_human"}],
    }
