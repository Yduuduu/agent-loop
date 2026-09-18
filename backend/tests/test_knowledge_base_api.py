"""POST /api/knowledge-base/documents → 진행 SSE → 실제 policy_rag_search 검색 경로
통합 테스트. 실제 임베딩 API를 호출하지 않도록 DeterministicFakeEmbedding +
임시 디렉터리 Chroma를 주입한다(임의 텍스트에 결정론적이지만 의미 없는 벡터를
부여하므로, "관련성 있게 검색되는가"가 아니라 "업로드한 청크가 실제 검색
경로(asimilarity_search)를 통해 조회 가능한가"를 검증하는 데 쓴다).
"""

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

from app.api.deps import get_vectorstore_builder
from app.main import app
from app.rag.retriever import search_policy_chunks

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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


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
