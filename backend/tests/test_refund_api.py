"""POST /api/refund-requests → GET .../stream → (필요 시) POST .../resume 통합 테스트.

httpx.AsyncClient + ASGITransport로 실제 서버 없이 SSE 스트림을 수신한다.
LLM은 fake로 치환해 네트워크 호출 없이 자동승인/자동거절/HITL 시나리오를 검증한다.
"""

import json

import httpx
import pytest

from app.agents.refund_agent.graph import build_graph
from app.agents.refund_agent.schemas import DamageAssessment, Decision
from app.api.deps import get_graph_builder
from app.main import app


async def approve_decide(
    order_data, damage_assessment, policy_findings, reference_date
) -> Decision:
    return Decision(
        decision="approve", reason="반품 기한 내 파손이 확인되었습니다.", confidence=0.9
    )


async def reject_decide(order_data, damage_assessment, policy_findings, reference_date) -> Decision:
    return Decision(decision="reject", reason="반품 기한이 지났습니다.", confidence=0.9)


async def damaged_assess(user_message: str, image_refs: list[str]) -> DamageAssessment:
    return DamageAssessment(
        is_damaged=True, severity="moderate", confidence=0.9, reasoning="파손 확인됨"
    )


async def fake_search_policy(query: str) -> list[dict]:
    return [{"text": "반품 기한은 14일이다.", "source": "refund_policy.pdf", "chunk_index": 0}]


def make_fake_order_lookup(order_id: str, total_amount: float = 89.0):
    async def fake_order_lookup(lookup_id: str) -> dict | None:
        if lookup_id != order_id:
            return None
        return {
            "order_id": order_id,
            "customer_email": "test@example.com",
            "purchased_at": "2026-09-12",
            "return_window_days": 14,
            "items": [
                {
                    "item_id": "ITEM-1",
                    "sku": "SKU-1",
                    "name": "상품",
                    "unit_price": total_amount,
                    "quantity": 1,
                }
            ],
            "total_amount": total_amount,
        }

    return fake_order_lookup


def override_graph_builder(
    *, order_id: str, total_amount: float = 89.0, decide=approve_decide
) -> None:
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda checkpointer: build_graph(
            order_lookup=make_fake_order_lookup(order_id, total_amount=total_amount),
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=decide,
            checkpointer=checkpointer,
        )
    )


async def _collect_stream_events(client: httpx.AsyncClient, case_id: str) -> list[dict]:
    events: list[dict] = []
    async with client.stream("GET", f"/api/refund-requests/{case_id}/stream") as response:
        assert response.status_code == 200
        event_type = None
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                events.append({"event": event_type, **payload})
    return events


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_auto_approve_scenario_streams_to_decision(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1001", decide=approve_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1001", "message": "파손된 채로 도착했습니다."},
    )
    assert create_resp.status_code == 200
    case_id = create_resp.json()["case_id"]

    events = await _collect_stream_events(client, case_id)

    event_types = [e["event"] for e in events]
    assert event_types[0] == "node_start"
    assert "tool_call" in event_types
    assert event_types[-1] == "decision"
    assert events[-1]["decision"] == "approve"
    assert events[-1]["requires_human"] is False

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == "completed"
    assert body["decision"] == "approve"


async def test_auto_reject_scenario_streams_to_decision(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1003", decide=reject_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1003", "message": "마음에 안 들어서 반품하고 싶어요."},
    )
    case_id = create_resp.json()["case_id"]

    events = await _collect_stream_events(client, case_id)

    assert events[-1]["event"] == "decision"
    assert events[-1]["decision"] == "reject"

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    assert status_resp.json()["status"] == "completed"


async def test_high_value_order_pauses_awaiting_human(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1002", total_amount=650.0, decide=approve_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1002", "message": "고액 상품 환불 요청입니다."},
    )
    case_id = create_resp.json()["case_id"]

    events = await _collect_stream_events(client, case_id)

    assert events[-1]["event"] == "awaiting_human"
    assert "고액" in events[-1]["reason"]

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    body = status_resp.json()
    assert body["status"] == "awaiting_human"
    assert body["requires_human"] is True
    assert body["flagged_reason"] is not None
    assert body["refund_amount"] == 650.0
    assert body["decision"] is None  # 아직 최종 판정 없음(재개 전)


async def test_resume_approve_completes_case(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1002", total_amount=650.0, decide=approve_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1002", "message": "고액 상품 환불 요청입니다."},
    )
    case_id = create_resp.json()["case_id"]
    await _collect_stream_events(client, case_id)  # 첫 레그를 끝까지 소비(awaiting_human)

    resume_resp = await client.post(
        f"/api/refund-requests/{case_id}/resume",
        json={"action": "approve", "admin_note": "관리자 확인 후 승인"},
    )
    assert resume_resp.status_code == 200
    assert resume_resp.json()["case_id"] == case_id

    events = await _collect_stream_events(client, case_id)
    assert events[-1]["event"] == "decision"
    assert events[-1]["decision"] == "approve"

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    body = status_resp.json()
    assert body["status"] == "completed"
    assert body["decision"] == "approve"
    assert body["decision_reason"] == "관리자 확인 후 승인"


async def test_resume_takeover_completes_case_with_resolved_decision(
    client: httpx.AsyncClient,
) -> None:
    override_graph_builder(order_id="ORD-1002", total_amount=650.0, decide=approve_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1002", "message": "고액 상품 환불 요청입니다."},
    )
    case_id = create_resp.json()["case_id"]
    await _collect_stream_events(client, case_id)

    resume_resp = await client.post(
        f"/api/refund-requests/{case_id}/resume",
        json={"action": "takeover", "admin_message": "고객과 협의해 부분 환불로 직접 처리함"},
    )
    assert resume_resp.status_code == 200
    await _collect_stream_events(client, case_id)

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    body = status_resp.json()
    assert body["status"] == "completed"
    assert body["decision"] == "resolved"
    assert body["decision_reason"] == "고객과 협의해 부분 환불로 직접 처리함"


async def test_resume_rejected_when_case_not_awaiting_human(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1001", decide=approve_decide)

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1001", "message": "파손된 채로 도착했습니다."},
    )
    case_id = create_resp.json()["case_id"]
    await _collect_stream_events(client, case_id)  # 자동 승인으로 completed까지 진행됨

    resume_resp = await client.post(
        f"/api/refund-requests/{case_id}/resume", json={"action": "approve"}
    )
    assert resume_resp.status_code == 409


async def test_list_refund_requests_filters_by_status(client: httpx.AsyncClient) -> None:
    override_graph_builder(order_id="ORD-1002", total_amount=650.0, decide=approve_decide)
    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1002", "message": "고액 상품 환불 요청입니다."},
    )
    case_id = create_resp.json()["case_id"]
    await _collect_stream_events(client, case_id)

    list_resp = await client.get("/api/refund-requests", params={"status": "awaiting_human"})
    assert list_resp.status_code == 200
    case_ids = [item["case_id"] for item in list_resp.json()]
    assert case_id in case_ids


async def test_order_not_found_emits_error_event(client: httpx.AsyncClient) -> None:
    async def missing_order_lookup(order_id: str) -> dict | None:
        return None

    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda checkpointer: build_graph(
            order_lookup=missing_order_lookup,
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=approve_decide,
            checkpointer=checkpointer,
        )
    )

    create_resp = await client.post(
        "/api/refund-requests", data={"order_id": "ORD-NOPE", "message": "환불해주세요"}
    )
    case_id = create_resp.json()["case_id"]

    events = await _collect_stream_events(client, case_id)

    assert events[-1]["event"] == "error"

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    assert status_resp.json()["status"] == "failed"


async def test_unknown_case_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/refund-requests/does-not-exist")
    assert resp.status_code == 404
