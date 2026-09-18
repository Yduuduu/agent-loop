"""RefundAgent StateGraph 시나리오 테스트.

실제 LLM을 호출하지 않고 order_lookup/assess_damage/search_policy/decide를
결정론적인 fake로 치환해 그래프 배선(order_lookup → damage_assessment →
policy_rag_search → decision → finalize|flag_for_human)과 라우팅 로직을 검증한다.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.agents.refund_agent.graph import build_graph
from app.agents.refund_agent.schemas import DamageAssessment, Decision
from app.agents.refund_agent.state import initial_state

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_orders.json"
FIXTURE_REFERENCE_DATE = date(2026, 9, 17)  # mock_orders.json의 _meta.generated_as_of와 일치

# image_quality → 가상 vision 모델이 반환했을 법한 파손 판정 (결정론적 매핑)
IMAGE_QUALITY_TO_ASSESSMENT = {
    "clear": DamageAssessment(
        is_damaged=True,
        severity="moderate",
        confidence=0.92,
        reasoning="증빙 사진이 선명하고 파손이 명확함",
    ),
    "n/a": DamageAssessment(
        is_damaged=False,
        severity="none",
        confidence=0.9,
        reasoning="파손 언급 없음, 단순 변심으로 보임",
    ),
    "blurry_ambiguous": DamageAssessment(
        is_damaged=True,
        severity="minor",
        confidence=0.35,
        reasoning="사진이 흐릿해 파손 여부를 확신할 수 없음",
    ),
}


def load_mock_orders() -> list[dict]:
    return json.loads(DATA_PATH.read_text())["orders"]


def order_payload_to_lookup_result(payload: dict) -> dict:
    return {
        "order_id": payload["order_id"],
        "customer_email": payload["customer_email"],
        "purchased_at": payload["purchased_at"],
        "return_window_days": payload["return_window_days"],
        "items": payload["items"],
        "total_amount": sum(item["unit_price"] * item["quantity"] for item in payload["items"]),
    }


def make_fake_order_lookup(order_payload: dict):
    lookup_result = order_payload_to_lookup_result(order_payload)

    async def fake_order_lookup(order_id: str) -> dict | None:
        return lookup_result if order_id == order_payload["order_id"] else None

    return fake_order_lookup


def make_fake_assess_damage(order_payload: dict):
    assessment = IMAGE_QUALITY_TO_ASSESSMENT[order_payload["refund_request"]["image_quality"]]

    async def fake_assess_damage(user_message: str, image_refs: list[str]) -> DamageAssessment:
        return assessment

    return fake_assess_damage


async def fake_search_policy(query: str) -> list[dict]:
    return [
        {
            "text": "반품 기한은 상품 수령일로부터 14일이다.",
            "source": "refund_policy.pdf",
            "chunk_index": 0,
        },
        {
            "text": "환불 금액이 500달러를 초과하면 사람 검토가 필요하다.",
            "source": "refund_policy.pdf",
            "chunk_index": 1,
        },
    ]


async def realistic_fake_decide(
    order_data: dict, damage_assessment: dict, policy_findings: list[dict], reference_date: str
) -> Decision:
    """실제 LLM이 DECISION_SYSTEM_PROMPT의 원칙을 그대로 따랐다면 내렸을 법한 결정을 흉내 낸다."""
    purchased_at = date.fromisoformat(order_data["purchased_at"])
    today = date.fromisoformat(reference_date)
    within_window = (today - purchased_at).days <= order_data["return_window_days"]
    is_damaged = damage_assessment.get("is_damaged", False)
    confidence = damage_assessment.get("confidence", 0.0)

    if not within_window and not is_damaged:
        return Decision(
            decision="reject", reason="반품 기한이 지났고 파손이 아닙니다.", confidence=0.9
        )
    if is_damaged and within_window and confidence >= 0.6:
        return Decision(
            decision="approve",
            reason="반품 기한 내 파손이 명확히 확인되었습니다.",
            confidence=confidence,
        )
    return Decision(
        decision="needs_human",
        reason="자동 판정 기준을 충족하지 않아 사람 검토가 필요합니다.",
        confidence=confidence or 0.5,
    )


@pytest.mark.parametrize("order_payload", load_mock_orders(), ids=lambda p: p["order_id"])
async def test_scenario_reaches_expected_decision(order_payload: dict) -> None:
    graph = build_graph(
        order_lookup=make_fake_order_lookup(order_payload),
        assess_damage=make_fake_assess_damage(order_payload),
        search_policy=fake_search_policy,
        decide=realistic_fake_decide,
        now_fn=lambda: FIXTURE_REFERENCE_DATE,
    )
    state = initial_state(
        order_id=order_payload["order_id"],
        user_message=order_payload["refund_request"]["user_message"],
        image_refs=order_payload["refund_request"]["image_refs"],
    )

    result = await graph.ainvoke(state)

    assert result["decision"] == order_payload["expected_decision"]
    assert result["requires_human"] == (order_payload["expected_decision"] == "needs_human")
    assert result["order_data"]["order_id"] == order_payload["order_id"]
    assert len(result["policy_findings"]) > 0
    assert len(result["messages"]) > 0


async def test_high_value_order_is_escalated_even_if_llm_would_approve() -> None:
    """LLM이 approve를 골라도 고액 기준을 넘으면 Python 라우팅이 사람 검토로 강제 전환해야 한다."""
    high_value_orders = [o for o in load_mock_orders() if o["order_id"] == "ORD-1002"]
    order_payload = high_value_orders[0]

    async def overconfident_decide(
        order_data, damage_assessment, policy_findings, reference_date
    ) -> Decision:
        return Decision(
            decision="approve", reason="테스트: LLM이 실수로 고액 건을 승인함", confidence=0.99
        )

    graph = build_graph(
        order_lookup=make_fake_order_lookup(order_payload),
        assess_damage=make_fake_assess_damage(order_payload),
        search_policy=fake_search_policy,
        decide=overconfident_decide,
        now_fn=lambda: FIXTURE_REFERENCE_DATE,
    )
    state = initial_state(
        order_id=order_payload["order_id"],
        user_message=order_payload["refund_request"]["user_message"],
        image_refs=order_payload["refund_request"]["image_refs"],
    )

    result = await graph.ainvoke(state)

    assert result["decision"] == "needs_human"
    assert result["requires_human"] is True
    assert "고액" in result["decision_reason"]


async def test_order_not_found_raises() -> None:
    graph = build_graph(
        order_lookup=make_fake_order_lookup(load_mock_orders()[0]),
        assess_damage=make_fake_assess_damage(load_mock_orders()[0]),
        search_policy=fake_search_policy,
        decide=realistic_fake_decide,
        now_fn=lambda: FIXTURE_REFERENCE_DATE,
    )
    state = initial_state(order_id="ORD-NOPE", user_message="환불해주세요", image_refs=[])

    with pytest.raises(ValueError, match="ORD-NOPE"):
        await graph.ainvoke(state)
