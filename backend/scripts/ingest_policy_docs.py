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

# scripts/generate_mock_policy_pdf.py가 만드는 대분류별 목업 문서. 여기 없는 파일
# (기존 refund_policy.pdf 등)은 미분류로 적재된다.
CATEGORY_BY_FILENAME = {
    "policy_class.pdf": "클래스",
    "policy_subscription.pdf": "콘텐츠 구독",
    "policy_book.pdf": "도서",
    "policy_package.pdf": "패키지·번들",
    "policy_payment_common.pdf": "결제·혜택 공통",
    "policy_exception.pdf": "예외·특수 상황",
}


async def main() -> None:
    results = await ingest_policy_docs_dir(
        POLICY_DOCS_DIR, categories_by_filename=CATEGORY_BY_FILENAME
    )
    if not results:
        print(f"no PDFs found in {POLICY_DOCS_DIR}")
        return

    async with async_session_factory() as session:
        for filename, chunk_count in results.items():
            product_category = CATEGORY_BY_FILENAME.get(filename)
            existing = await session.scalar(
                select(PolicyDocument).where(PolicyDocument.filename == filename)
            )
            if existing:
                existing.chunk_count = chunk_count
                existing.status = "indexed"
                existing.product_category = product_category
            else:
                session.add(
                    PolicyDocument(
                        filename=filename,
                        product_category=product_category,
                        status="indexed",
                        chunk_count=chunk_count,
                    )
                )
            print(f"  - {filename}: {chunk_count} chunks indexed")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
