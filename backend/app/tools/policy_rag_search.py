from app.rag.retriever import search_policy_chunks


async def search_policy(query: str, *, k: int = 4) -> list[dict]:
    """케이스 기반 쿼리로 관련 정책 청크 top-k를 검색한다."""
    docs = await search_policy_chunks(query, k=k)
    return [
        {
            "text": doc.page_content,
            "source": doc.metadata.get("source"),
            "chunk_index": doc.metadata.get("chunk_index"),
        }
        for doc in docs
    ]
