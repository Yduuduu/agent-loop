from collections.abc import Awaitable, Callable
from pathlib import Path

from langchain_chroma import Chroma
from pypdf import PdfReader

from app.rag.chunking import split_text
from app.rag.retriever import get_vectorstore

# (stage, data) -> None. stage: "chunking" | "embedding" | "indexed"
ProgressFn = Callable[[str, dict], Awaitable[None]]


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


async def ingest_pdf(
    path: Path,
    *,
    doc_id: str | None = None,
    vectorstore: Chroma | None = None,
    on_progress: ProgressFn | None = None,
) -> int:
    """PDF 한 건을 청킹 후 벡터스토어에 적재하고 청크 수를 반환한다.

    doc_id는 벡터 id 접두어로 쓰인다 — 같은 파일명을 여러 번 업로드해도
    (additive 버전 관리, 이전 청크를 덮어쓰지 않음) 서로 다른 doc_id면
    id가 충돌하지 않는다. 넘기지 않으면 파일명(stem)을 쓴다(Phase 1 CLI 벌크
    적재처럼 doc_id 개념이 없는 경로용).
    """

    async def emit(stage: str, data: dict) -> None:
        if on_progress:
            await on_progress(stage, data)

    id_prefix = doc_id or path.stem

    await emit("chunking", {})
    text = extract_pdf_text(path)
    chunks = split_text(text)
    if not chunks:
        raise ValueError(f"{path.name}에서 추출할 텍스트가 없습니다")

    await emit("embedding", {"chunk_count": len(chunks)})
    store = vectorstore or get_vectorstore()
    ids = [f"{id_prefix}-{i}" for i in range(len(chunks))]
    metadatas = [
        {"source": path.name, "chunk_index": i, "doc_id": id_prefix} for i in range(len(chunks))
    ]
    await store.aadd_texts(texts=chunks, metadatas=metadatas, ids=ids)

    await emit("indexed", {"chunk_count": len(chunks)})
    return len(chunks)


async def ingest_policy_docs_dir(dir_path: Path) -> dict[str, int]:
    """dir_path 내 모든 PDF를 적재하고 {파일명: 청크수}를 반환한다.

    파일 하나가 실패해도(예: 텍스트 추출 불가) 나머지 파일은 계속 처리한다.
    """
    results: dict[str, int] = {}
    for pdf_path in sorted(dir_path.glob("*.pdf")):
        try:
            results[pdf_path.name] = await ingest_pdf(pdf_path)
        except ValueError as exc:
            print(f"  ! {pdf_path.name} 건너뜀: {exc}")
    return results
