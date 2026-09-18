from pathlib import Path

from pypdf import PdfReader

from app.rag.chunking import split_text
from app.rag.retriever import get_vectorstore


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


async def ingest_pdf(path: Path) -> int:
    """PDF 한 건을 청킹 후 벡터스토어에 적재하고 청크 수를 반환한다."""
    text = extract_pdf_text(path)
    chunks = split_text(text)
    if not chunks:
        return 0

    vectorstore = get_vectorstore()
    ids = [f"{path.stem}-{i}" for i in range(len(chunks))]
    metadatas = [{"source": path.name, "chunk_index": i} for i in range(len(chunks))]
    await vectorstore.aadd_texts(texts=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


async def ingest_policy_docs_dir(dir_path: Path) -> dict[str, int]:
    """dir_path 내 모든 PDF를 적재하고 {파일명: 청크수}를 반환한다."""
    results: dict[str, int] = {}
    for pdf_path in sorted(dir_path.glob("*.pdf")):
        results[pdf_path.name] = await ingest_pdf(pdf_path)
    return results
