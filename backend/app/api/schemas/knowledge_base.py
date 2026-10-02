from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.rag.policy_summarizer import PolicyItem


class KBDocumentCreateResponse(BaseModel):
    doc_id: str


class KBDocumentResponse(BaseModel):
    doc_id: str
    filename: str
    # 대분류 한국어 라벨. None이면 미분류.
    product_category: str | None = None
    status: Literal["uploaded", "chunking", "embedding", "indexed", "failed"]
    progress_pct: int
    chunk_count: int
    created_at: datetime
    policy_summary_status: Literal["pending", "summarizing", "done", "failed"]
    policy_summary: list[PolicyItem] | None = None


class PolicyGroup(BaseModel):
    # 대시보드는 (대분류, 소분류) 단위로 묶는다. 미분류 문서는 product_category="미분류".
    product_category: str
    policy_type: str
    items: list[PolicyItem]


class PolicyCategoryResponse(BaseModel):
    product_category: str
    policy_types: list[str]
