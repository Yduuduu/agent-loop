"""RefundAgent StateGraph 시나리오 테스트.

실제 LLM을 호출하지 않고 order_lookup/assess_damage/search_policy/decide를
결정론적인 fake로 치환해 그래프 배선(order_lookup → damage_assessment →
policy_rag_search → decision → finalize|flag_for_human)과 라우팅 로직을 검증한다.

Phase 3: flag_for_human은 interrupt()로 실행을 진짜 중단하므로, 체크포인터가
항상 필요하고(build_graph() 기본값인 InMemorySaver로 충분) 모든 호출에
thread_id가 있는 config가 필요하다.
"""

import json
import tempfile
import uuid
from datetime import date
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

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


def _thread_config() -> dict:
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


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

    result = await graph.ainvoke(state, config=_thread_config())

    if order_payload["expected_decision"] == "needs_human":
        # flag_for_human이 interrupt()로 진짜 멈춘다 — 최종 판정은 resume 이후에야 난다
        # (resume 흐름은 test_resume_* 테스트에서 별도로 검증).
        assert "__interrupt__" in result
    else:
        assert "__interrupt__" not in result
        assert result["decision"] == order_payload["expected_decision"]
        assert result["requires_human"] is False

    assert result["order_data"]["order_id"] == order_payload["order_id"]
    assert len(result["policy_findings"]) > 0
    assert len(result["messages"]) > 0


async def test_high_value_order_is_escalated_even_if_llm_would_approve() -> None:
    """LLM이 approve를 골라도 고액 기준을 넘으면 Python 라우팅이 interrupt()로 멈춰야 한다."""
    order_payload = next(o for o in load_mock_orders() if o["order_id"] == "ORD-1002")

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

    result = await graph.ainvoke(state, config=_thread_config())

    assert "__interrupt__" in result
    interrupt_payload = result["__interrupt__"][0].value
    assert "고액" in interrupt_payload["reason"]
    assert interrupt_payload["suggested_decision"] == "approve"


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
        await graph.ainvoke(state, config=_thread_config())


def _high_value_graph_and_state():
    order_payload = next(o for o in load_mock_orders() if o["order_id"] == "ORD-1002")
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
    return graph, state


async def test_resume_approve_produces_final_approve_decision() -> None:
    graph, state = _high_value_graph_and_state()
    config = _thread_config()

    paused = await graph.ainvoke(state, config=config)
    assert "__interrupt__" in paused

    result = await graph.ainvoke(
        Command(resume={"action": "approve", "admin_note": "관리자가 직접 확인 후 승인"}),
        config=config,
    )

    assert "__interrupt__" not in result
    assert result["decision"] == "approve"
    assert result["decision_reason"] == "관리자가 직접 확인 후 승인"
    assert result["requires_human"] is False


async def test_resume_reject_produces_final_reject_decision() -> None:
    graph, state = _high_value_graph_and_state()
    config = _thread_config()

    await graph.ainvoke(state, config=config)
    result = await graph.ainvoke(
        Command(resume={"action": "reject", "admin_note": "정책상 환불 불가로 판단"}), config=config
    )

    assert result["decision"] == "reject"
    assert result["decision_reason"] == "정책상 환불 불가로 판단"


async def test_resume_takeover_produces_resolved_decision_without_reasoning() -> None:
    """takeover는 그래프가 재추론하지 않고 관리자 메시지가 바로 최종 사유가 된다."""
    graph, state = _high_value_graph_and_state()
    config = _thread_config()

    await graph.ainvoke(state, config=config)
    result = await graph.ainvoke(
        Command(
            resume={"action": "takeover", "admin_message": "고객과 직접 협의해 부분 환불로 처리함"}
        ),
        config=config,
    )

    assert result["decision"] == "resolved"
    assert result["decision_reason"] == "고객과 직접 협의해 부분 환불로 처리함"


async def test_checkpointer_persists_across_simulated_process_restart() -> None:
    """일시정지 - (프로세스 재시작 시뮬레이션: 체크포인터 연결을 완전히 닫고 새로 연다) - 재개.

    AsyncSqliteSaver가 같은 파일을 다시 열었을 때도 중단 지점부터 재개되는지
    증명한다 — Phase 3 exit criteria의 핵심 검증 포인트.
    """
    order_payload = next(o for o in load_mock_orders() if o["order_id"] == "ORD-1002")
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "checkpoint_restart_test.db")

        async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
            graph = build_graph(
                order_lookup=make_fake_order_lookup(order_payload),
                assess_damage=make_fake_assess_damage(order_payload),
                search_policy=fake_search_policy,
                decide=realistic_fake_decide,
                now_fn=lambda: FIXTURE_REFERENCE_DATE,
                checkpointer=checkpointer,
            )
            state = initial_state(
                order_id=order_payload["order_id"],
                user_message=order_payload["refund_request"]["user_message"],
                image_refs=order_payload["refund_request"]["image_refs"],
            )
            paused = await graph.ainvoke(state, config=config)
            assert "__interrupt__" in paused
        # 여기서 checkpointer 연결이 완전히 닫힌다 — 새 연결을 여는 것으로
        # "프로세스 재시작"을 시뮬레이션한다(이 프로세스의 메모리 상태는
        # 이미 사용하지 않고, 디스크의 체크포인트 파일만 신뢰한다).

        async with AsyncSqliteSaver.from_conn_string(db_path) as fresh_checkpointer:
            fresh_graph = build_graph(
                order_lookup=make_fake_order_lookup(order_payload),
                assess_damage=make_fake_assess_damage(order_payload),
                search_policy=fake_search_policy,
                decide=realistic_fake_decide,
                now_fn=lambda: FIXTURE_REFERENCE_DATE,
                checkpointer=fresh_checkpointer,
            )
            result = await fresh_graph.ainvoke(
                Command(resume={"action": "approve", "admin_note": "재시작 후 재개 승인"}),
                config=config,
            )

    assert "__interrupt__" not in result
    assert result["decision"] == "approve"
    assert result["decision_reason"] == "재시작 후 재개 승인"
