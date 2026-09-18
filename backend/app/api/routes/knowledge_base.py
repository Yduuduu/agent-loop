import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api import event_bus
from app.api.deps import SessionDep, VectorstoreBuilderDep
from app.api.kb_runner import run_ingestion
from app.api.schemas.knowledge_base import KBDocumentCreateResponse, KBDocumentResponse
from app.core.config import get_settings
from app.db.models import PolicyDocument

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

# fire-and-forget 백그라운드 태스크가 GC되지 않도록 강한 참조를 유지한다.
_background_tasks: set[asyncio.Task] = set()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

FileUpload = Annotated[UploadFile, File()]


@router.post("/documents", response_model=KBDocumentCreateResponse)
async def upload_document(
    session: SessionDep,
    build_vectorstore: VectorstoreBuilderDep,
    file: FileUpload,
) -> KBDocumentCreateResponse:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="파일이 너무 큽니다 (최대 20MB)")
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다")

    doc = PolicyDocument(filename=file.filename, status="uploaded", progress_pct=0, chunk_count=0)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    settings = get_settings()
    dest_dir = Path(settings.policy_docs_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # doc_id를 파일명에 접두해 동일 파일명 재업로드가 기존 원본을 덮어쓰지 않게 한다
    # (버전 관리는 MVP 범위 밖 — additive만 지원).
    dest_path = dest_dir / f"{doc.doc_id}-{file.filename}"
    dest_path.write_bytes(content)

    event_bus.create_queue(f"kb:{doc.doc_id}")
    task = asyncio.create_task(run_ingestion(doc.doc_id, dest_path, build_vectorstore))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return KBDocumentCreateResponse(doc_id=doc.doc_id)


@router.get("/documents", response_model=list[KBDocumentResponse])
async def list_documents(session: SessionDep) -> list[KBDocumentResponse]:
    docs = (
        await session.scalars(select(PolicyDocument).order_by(PolicyDocument.created_at.desc()))
    ).all()
    return [_to_response(doc) for doc in docs]


@router.get("/documents/{doc_id}/stream")
async def stream_document(doc_id: str, session: SessionDep) -> StreamingResponse:
    doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")

    key = f"kb:{doc_id}"
    queue = event_bus.get_queue(key)
    if queue is None:
        raise HTTPException(
            status_code=410, detail="stream unavailable (already consumed or not started)"
        )

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is event_bus.STREAM_DONE:
                    break
                yield item.to_wire()
        finally:
            event_bus.remove_queue(key)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/documents/{doc_id}", response_model=KBDocumentResponse)
async def get_document(doc_id: str, session: SessionDep) -> KBDocumentResponse:
    doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _to_response(doc)


def _to_response(doc: PolicyDocument) -> KBDocumentResponse:
    return KBDocumentResponse(
        doc_id=doc.doc_id,
        filename=doc.filename,
        status=doc.status,
        progress_pct=doc.progress_pct,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
    )
