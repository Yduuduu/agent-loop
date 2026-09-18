"""POST /api/refund-requests → GET /api/refund-requests/{case_id}/stream 통합 테스트.

httpx.AsyncClient + ASGITransport로 실제 서버 없이 SSE 스트림을 수신한다.
LLM은 fake로 치환해 네트워크 호출 없이 자동승인/자동거절 시나리오를 검증한다.
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
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda: build_graph(
            order_lookup=make_fake_order_lookup("ORD-1001"),
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=approve_decide,
        )
    )

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
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda: build_graph(
            order_lookup=make_fake_order_lookup("ORD-1003"),
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=reject_decide,
        )
    )

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


async def test_high_value_order_ends_awaiting_human(client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda: build_graph(
            order_lookup=make_fake_order_lookup("ORD-1002", total_amount=650.0),
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=approve_decide,
        )
    )

    create_resp = await client.post(
        "/api/refund-requests",
        data={"order_id": "ORD-1002", "message": "고액 상품 환불 요청입니다."},
    )
    case_id = create_resp.json()["case_id"]

    events = await _collect_stream_events(client, case_id)

    assert events[-1]["event"] == "decision"
    assert events[-1]["decision"] == "needs_human"
    assert events[-1]["requires_human"] is True

    status_resp = await client.get(f"/api/refund-requests/{case_id}")
    body = status_resp.json()
    assert body["status"] == "awaiting_human"
    assert body["flagged_reason"] is not None


async def test_order_not_found_emits_error_event(client: httpx.AsyncClient) -> None:
    async def missing_order_lookup(order_id: str) -> dict | None:
        return None

    app.dependency_overrides[get_graph_builder] = lambda: (
        lambda: build_graph(
            order_lookup=missing_order_lookup,
            assess_damage=damaged_assess,
            search_policy=fake_search_policy,
            decide=approve_decide,
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
