from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import get_settings

COLLECTION_NAME = "refund_policy"


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    settings = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", google_api_key=settings.google_api_key
    )


@lru_cache
def get_vectorstore() -> Chroma:
    settings = get_settings()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_persist_dir,
    )


async def search_policy_chunks(query: str, *, k: int = 4) -> list[Document]:
    vectorstore = get_vectorstore()
    return await vectorstore.asimilarity_search(query, k=k)
