from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.rag.policy_summarizer import PolicyItem


class KBDocumentCreateResponse(BaseModel):
    doc_id: str


class KBDocumentResponse(BaseModel):
    doc_id: str
    filename: str
    status: Literal["uploaded", "chunking", "embedding", "indexed", "failed"]
    progress_pct: int
    chunk_count: int
    created_at: datetime
    policy_summary_status: Literal["pending", "summarizing", "done", "failed"]
    policy_summary: list[PolicyItem] | None = None


class PolicyGroup(BaseModel):
    category: str
    items: list[PolicyItem]
