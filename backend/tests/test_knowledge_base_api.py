"""POST /api/knowledge-base/documents → 진행 SSE → 실제 policy_rag_search 검색 경로
통합 테스트. 실제 임베딩 API를 호출하지 않도록 DeterministicFakeEmbedding +
임시 디렉터리 Chroma를 주입한다(임의 텍스트에 결정론적이지만 의미 없는 벡터를
부여하므로, "관련성 있게 검색되는가"가 아니라 "업로드한 청크가 실제 검색
경로(asimilarity_search)를 통해 조회 가능한가"를 검증하는 데 쓴다).
"""

import asyncio
import json
import tempfile
from pathlib import Path

import httpx
import pytest
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import select

from app.api.deps import get_policy_summarizer, get_vectorstore_builder
from app.core.config import get_settings
from app.db.models import PolicyDocument
from app.db.session import async_session_factory
from app.main import app
from app.rag.policy_summarizer import PolicyItem
from app.rag.retriever import search_policy_chunks

FAKE_POLICY_ITEMS = [
    PolicyItem(
        category="환불기한",
        title="7일 이내 무료 반품",
        summary="테스트 정책 요약입니다.",
        source_excerpt="AgentOps 테스트 정책 문서입니다.",
    )
]


async def fake_summarize(_document_text: str) -> list[PolicyItem]:
    return FAKE_POLICY_ITEMS

FONT_NAME = "HYSMyeongJo-Medium"


def make_test_pdf(path: Path, *, lines: list[str]) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    c = canvas.Canvas(str(path))
    c.setFont(FONT_NAME, 12)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()


@pytest.fixture
def test_vectorstore():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Chroma(
            collection_name="kb_test",
            embedding_function=DeterministicFakeEmbedding(size=32),
            persist_directory=tmpdir,
        )


@pytest.fixture
async def client(test_vectorstore):
    app.dependency_overrides[get_vectorstore_builder] = lambda: (lambda: test_vectorstore)
    app.dependency_overrides[get_policy_summarizer] = lambda: fake_summarize
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _upload_and_wait(client: httpx.AsyncClient, pdf_path: Path, filename: str) -> str:
    with pdf_path.open("rb") as f:
        create_resp = await client.post(
            "/api/knowledge-base/documents",
            files={"file": (filename, f, "application/pdf")},
        )
    doc_id = create_resp.json()["doc_id"]
    await _collect_stream_events(client, doc_id)
    return doc_id


async def _wait_for_policy_summary_status(
    client: httpx.AsyncClient, doc_id: str, *, attempts: int = 50
) -> dict:
    for _ in range(attempts):
        body = (await client.get(f"/api/knowledge-base/documents/{doc_id}")).json()
        if body["policy_summary_status"] in ("done", "failed"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError("정책 요약이 시간 내에 완료되지 않았습니다")


async def _collect_stream_events(client: httpx.AsyncClient, doc_id: str) -> list[dict]:
    events: list[dict] = []
    async with client.stream("GET", f"/api/knowledge-base/documents/{doc_id}/stream") as response:
        assert response.status_code == 200
        event_type = None
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                events.append({"event": event_type, **payload})
    return events


async def test_upload_streams_progress_and_becomes_searchable(
    client: httpx.AsyncClient, test_vectorstore: Chroma, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "refund_policy_test.pdf"
    make_test_pdf(
        pdf_path, lines=["AgentOps 테스트 정책 문서입니다.", "이 문장은 검색 가능해야 합니다."]
    )

    with pdf_path.open("rb") as f:
        create_resp = await client.post(
            "/api/knowledge-base/documents",
            files={"file": ("refund_policy_test.pdf", f, "application/pdf")},
        )
    assert create_resp.status_code == 200
    doc_id = create_resp.json()["doc_id"]

    events = await _collect_stream_events(client, doc_id)
    event_types = [e["event"] for e in events]

    assert event_types == ["chunking", "embedding", "indexed"]
    assert events[0]["progress_pct"] == 25
    assert events[1]["progress_pct"] == 60
    assert events[2]["progress_pct"] == 100
    assert events[2]["chunk_count"] >= 1

    status_resp = await client.get(f"/api/knowledge-base/documents/{doc_id}")
    body = status_resp.json()
    assert body["status"] == "indexed"
    assert body["progress_pct"] == 100
    assert body["chunk_count"] >= 1

    # 핵심 검증: "업로드됨" 표시가 아니라 실제 policy_rag_search 경로(asimilarity_search)로
    # 이 문서의 청크가 조회되는지 확인한다. k를 크게 잡아 새로 넣은 소수의 청크를 모두 포함시킨다.
    results = await search_policy_chunks("아무 질의", k=50, vectorstore=test_vectorstore)
    matching = [r for r in results if r.metadata.get("doc_id") == doc_id]
    assert len(matching) >= 1
    assert any("AgentOps 테스트 정책" in r.page_content for r in matching)


async def test_list_documents_reflects_upload(
    client: httpx.AsyncClient, test_vectorstore: Chroma, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "another_policy.pdf"
    make_test_pdf(pdf_path, lines=["또 다른 정책 문서."])

    with pdf_path.open("rb") as f:
        create_resp = await client.post(
            "/api/knowledge-base/documents",
            files={"file": ("another_policy.pdf", f, "application/pdf")},
        )
    doc_id = create_resp.json()["doc_id"]
    await _collect_stream_events(client, doc_id)

    list_resp = await client.get("/api/knowledge-base/documents")
    assert list_resp.status_code == 200
    doc_ids = [d["doc_id"] for d in list_resp.json()]
    assert doc_id in doc_ids


async def test_rejects_non_pdf_upload(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/knowledge-base/documents",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )
    assert resp.status_code == 400


async def test_rejects_empty_pdf_upload(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/knowledge-base/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


async def test_unknown_document_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/knowledge-base/documents/does-not-exist")
    assert resp.status_code == 404


async def test_get_document_file_returns_pdf_bytes(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "viewable.pdf"
    make_test_pdf(pdf_path, lines=["열람 테스트 문서."])
    doc_id = await _upload_and_wait(client, pdf_path, "viewable.pdf")

    resp = await client.get(f"/api/knowledge-base/documents/{doc_id}/file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == pdf_path.read_bytes()


async def test_get_document_file_unknown_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/knowledge-base/documents/does-not-exist/file")
    assert resp.status_code == 404


async def test_delete_document_removes_row_file_and_vectors(
    client: httpx.AsyncClient, test_vectorstore: Chroma, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "deletable.pdf"
    make_test_pdf(pdf_path, lines=["삭제 테스트 문서입니다."])
    doc_id = await _upload_and_wait(client, pdf_path, "deletable.pdf")

    status_resp = await client.get(f"/api/knowledge-base/documents/{doc_id}")
    # file_path는 API 응답에 노출하지 않으므로 디스크에서 직접 확인한다.
    stored_path = Path(get_settings().policy_docs_dir)
    assert status_resp.json()["chunk_count"] >= 1

    delete_resp = await client.delete(f"/api/knowledge-base/documents/{doc_id}")
    assert delete_resp.status_code == 204

    assert (await client.get(f"/api/knowledge-base/documents/{doc_id}")).status_code == 404
    assert (await client.get(f"/api/knowledge-base/documents/{doc_id}/file")).status_code == 404

    remaining = await search_policy_chunks("아무 질의", k=50, vectorstore=test_vectorstore)
    assert all(r.metadata.get("doc_id") != doc_id for r in remaining)

    # 업로드된 원본 파일도 디스크에서 제거됐는지 확인
    leftover = list(stored_path.glob(f"{doc_id}-*"))
    assert leftover == []


async def test_delete_unknown_document_returns_404(client: httpx.AsyncClient) -> None:
    resp = await client.delete("/api/knowledge-base/documents/does-not-exist")
    assert resp.status_code == 404


async def test_delete_document_in_progress_returns_409(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    # 백그라운드 인제스천 완료와의 경합을 피하려고, 업로드 후 DB 상태를 직접
    # "chunking"(비종료 상태)으로 고정해 두고 삭제를 시도한다.
    pdf_path = tmp_path / "in_progress.pdf"
    make_test_pdf(pdf_path, lines=["진행 중 문서."])
    with pdf_path.open("rb") as f:
        resp = await client.post(
            "/api/knowledge-base/documents",
            files={"file": ("in_progress.pdf", f, "application/pdf")},
        )
    doc_id = resp.json()["doc_id"]
    await _collect_stream_events(client, doc_id)  # 인제스천 완료까지 대기 후

    async with async_session_factory() as session:
        doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
        assert doc is not None
        doc.status = "chunking"  # 비종료 상태로 강제 고정
        await session.commit()

    delete_resp = await client.delete(f"/api/knowledge-base/documents/{doc_id}")
    assert delete_resp.status_code == 409


async def test_policy_summary_populates_after_indexing_and_policies_endpoint_groups_by_category(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "policy_summary.pdf"
    make_test_pdf(pdf_path, lines=["정책 요약 테스트 문서."])
    doc_id = await _upload_and_wait(client, pdf_path, "policy_summary.pdf")

    body = await _wait_for_policy_summary_status(client, doc_id)
    assert body["policy_summary_status"] == "done"
    assert body["policy_summary"] == [item.model_dump() for item in FAKE_POLICY_ITEMS]

    policies_resp = await client.get("/api/knowledge-base/policies")
    assert policies_resp.status_code == 200
    groups = {g["category"]: g["items"] for g in policies_resp.json()}
    assert "환불기한" in groups
    assert any(item["title"] == "7일 이내 무료 반품" for item in groups["환불기한"])
