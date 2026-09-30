"""지식베이스 PDF 인제스천을 실행하며 진행 상황을 SSE 이벤트로 발행하고
PolicyDocument 상태를 DB에 반영한다. refund_runner.py와 같은 어댑터 패턴 —
app/rag/ingest.py의 on_progress 콜백을 KBEvent로 변환해 event_bus에 발행한다.
"""

from pathlib import Path

from langchain_chroma import Chroma
from sqlalchemy import select

from app.api import event_bus
from app.api.deps import VectorstoreBuilder
from app.api.schemas.kb_events import KBEvent, KBEventType
from app.db.models import PolicyDocument
from app.db.session import async_session_factory
from app.rag.ingest import extract_pdf_text, ingest_pdf
from app.rag.policy_summarizer import SummarizeFn

# app/rag/ingest.py의 on_progress(stage, data) stage 값과 1:1로 대응한다.
STAGE_PROGRESS = {
    "chunking": 25,
    "embedding": 60,
    "indexed": 100,
}


def _stream_key(doc_id: str) -> str:
    return f"kb:{doc_id}"


async def run_ingestion(
    doc_id: str,
    pdf_path: Path,
    build_vectorstore: VectorstoreBuilder,
    summarize: SummarizeFn,
) -> None:
    key = _stream_key(doc_id)
    vectorstore: Chroma = build_vectorstore()

    async def on_progress(stage: str, data: dict) -> None:
        pct = STAGE_PROGRESS.get(stage, 0)
        chunk_count = data.get("chunk_count")
        await _persist(doc_id, status=stage, progress_pct=pct, chunk_count=chunk_count)
        await event_bus.publish(
            key,
            KBEvent(event=KBEventType(stage), doc_id=doc_id, data={"progress_pct": pct, **data}),
        )

    try:
        await ingest_pdf(pdf_path, doc_id=doc_id, vectorstore=vectorstore, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001 — 원인 불문 failed 이벤트로 알리고 상태를 failed로
        await _persist(doc_id, status="failed", progress_pct=None, chunk_count=None)
        await event_bus.publish(
            key, KBEvent(event=KBEventType.FAILED, doc_id=doc_id, data={"message": str(exc)})
        )
        return
    finally:
        await event_bus.publish_done(key)

    # 정책 요약은 인제스천 상태 머신과 분리된 후처리라, 실패해도 문서의
    # 검색 가능 여부(indexed)에는 영향을 주지 않는다.
    await run_policy_summarization(doc_id, pdf_path, summarize)


async def run_policy_summarization(doc_id: str, pdf_path: Path, summarize: SummarizeFn) -> None:
    await _persist_policy_summary_status(doc_id, "summarizing")
    try:
        text = extract_pdf_text(pdf_path)
        items = await summarize(text)
        await _persist_policy_summary(
            doc_id, status="done", summary=[item.model_dump() for item in items]
        )
    except Exception:  # noqa: BLE001 — 요약 실패는 문서 자체를 실패시키지 않는다
        await _persist_policy_summary_status(doc_id, "failed")


async def _persist(
    doc_id: str, *, status: str, progress_pct: int | None, chunk_count: int | None
) -> None:
    async with async_session_factory() as session:
        doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
        assert doc is not None
        doc.status = status
        if progress_pct is not None:
            doc.progress_pct = progress_pct
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        await session.commit()


async def _persist_policy_summary_status(doc_id: str, status: str) -> None:
    async with async_session_factory() as session:
        doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
        assert doc is not None
        doc.policy_summary_status = status
        await session.commit()


async def _persist_policy_summary(doc_id: str, *, status: str, summary: list[dict]) -> None:
    async with async_session_factory() as session:
        doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
        assert doc is not None
        doc.policy_summary_status = status
        doc.policy_summary = summary
        await session.commit()
