"""backend/data/policy_docs/*.pdf를 청킹 → 임베딩 → ChromaDB에 적재하고
PolicyDocument 레코드를 남긴다. RAG 검색(policy_rag_search)이 동작하려면
run_agent_cli.py 실행 전에 이 스크립트를 한 번 실행해야 한다.
"""

import asyncio
from pathlib import Path

from sqlalchemy import select

from app.db.models import PolicyDocument
from app.db.session import async_session_factory
from app.rag.ingest import ingest_policy_docs_dir

POLICY_DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "policy_docs"


async def main() -> None:
    results = await ingest_policy_docs_dir(POLICY_DOCS_DIR)
    if not results:
        print(f"no PDFs found in {POLICY_DOCS_DIR}")
        return

    async with async_session_factory() as session:
        for filename, chunk_count in results.items():
            existing = await session.scalar(
                select(PolicyDocument).where(PolicyDocument.filename == filename)
            )
            if existing:
                existing.chunk_count = chunk_count
                existing.status = "indexed"
            else:
                session.add(
                    PolicyDocument(filename=filename, status="indexed", chunk_count=chunk_count)
                )
            print(f"  - {filename}: {chunk_count} chunks indexed")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
