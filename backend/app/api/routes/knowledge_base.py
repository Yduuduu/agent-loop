import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from app.api import event_bus
from app.api.deps import PolicySummarizerDep, SessionDep, VectorstoreBuilderDep, require_admin_auth
from app.api.kb_runner import run_ingestion
from app.api.schemas.knowledge_base import (
    KBDocumentCreateResponse,
    KBDocumentResponse,
    PolicyGroup,
    PolicyItem,
)
from app.core.config import get_settings
from app.core.security import sanitize_filename
from app.db.models import PolicyDocument

router = APIRouter(
    prefix="/api/knowledge-base",
    tags=["knowledge-base"],
    dependencies=[Depends(require_admin_auth)],
)

# 인제스천이 아직 끝나지 않은 문서는 파일/벡터가 쓰기 중일 수 있어 삭제를 막는다.
INGESTION_TERMINAL_STATUSES = {"indexed", "failed"}

# fire-and-forget 백그라운드 태스크가 GC되지 않도록 강한 참조를 유지한다.
_background_tasks: set[asyncio.Task] = set()

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PDF_MAGIC = b"%PDF-"

FileUpload = Annotated[UploadFile, File()]


@router.post("/documents", response_model=KBDocumentCreateResponse)
async def upload_document(
    session: SessionDep,
    build_vectorstore: VectorstoreBuilderDep,
    summarize_policy: PolicySummarizerDep,
    file: FileUpload,
) -> KBDocumentCreateResponse:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다")

    safe_filename = sanitize_filename(file.filename or "")
    if not safe_filename:
        raise HTTPException(status_code=400, detail="올바르지 않은 파일명입니다")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="파일이 너무 큽니다 (최대 20MB)")
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다")
    # 확장자만으로는 실제 내용을 보장할 수 없다 — PDF 매직 바이트를 직접 확인한다.
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="유효한 PDF 파일이 아닙니다")

    doc = PolicyDocument(filename=safe_filename, status="uploaded", progress_pct=0, chunk_count=0)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    settings = get_settings()
    dest_dir = Path(settings.policy_docs_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # doc_id를 파일명에 접두해 동일 파일명 재업로드가 기존 원본을 덮어쓰지 않게 한다
    # (버전 관리는 MVP 범위 밖 — additive만 지원).
    dest_path = dest_dir / f"{doc.doc_id}-{safe_filename}"
    dest_path.write_bytes(content)
    doc.file_path = str(dest_path)
    await session.commit()

    event_bus.create_queue(f"kb:{doc.doc_id}")
    task = asyncio.create_task(
        run_ingestion(doc.doc_id, dest_path, build_vectorstore, summarize_policy)
    )
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


@router.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str, session: SessionDep) -> FileResponse:
    doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    if not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(status_code=404, detail="file not found on disk")
    return FileResponse(doc.file_path, media_type="application/pdf", filename=doc.filename)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str, session: SessionDep, build_vectorstore: VectorstoreBuilderDep
) -> None:
    doc = await session.scalar(select(PolicyDocument).where(PolicyDocument.doc_id == doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status not in INGESTION_TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409, detail="인제스천이 진행 중인 문서는 삭제할 수 없습니다"
        )

    if doc.chunk_count:
        vectorstore = build_vectorstore()
        ids = [f"{doc_id}-{i}" for i in range(doc.chunk_count)]
        await vectorstore.adelete(ids=ids)

    if doc.file_path:
        Path(doc.file_path).unlink(missing_ok=True)

    event_bus.remove_queue(f"kb:{doc_id}")
    await session.delete(doc)
    await session.commit()


@router.get("/policies", response_model=list[PolicyGroup])
async def list_policies(session: SessionDep) -> list[PolicyGroup]:
    docs = (
        await session.scalars(
            select(PolicyDocument).where(PolicyDocument.policy_summary_status == "done")
        )
    ).all()

    grouped: dict[str, list[PolicyItem]] = defaultdict(list)
    for doc in docs:
        for raw_item in doc.policy_summary or []:
            grouped[raw_item["category"]].append(PolicyItem(**raw_item))

    return [PolicyGroup(category=category, items=items) for category, items in grouped.items()]


def _to_response(doc: PolicyDocument) -> KBDocumentResponse:
    return KBDocumentResponse(
        doc_id=doc.doc_id,
        filename=doc.filename,
        status=doc.status,
        progress_pct=doc.progress_pct,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        policy_summary_status=doc.policy_summary_status,
        policy_summary=[PolicyItem(**item) for item in doc.policy_summary]
        if doc.policy_summary
        else None,
    )
