from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class KBDocumentCreateResponse(BaseModel):
    doc_id: str


class KBDocumentResponse(BaseModel):
    doc_id: str
    filename: str
    status: Literal["uploaded", "chunking", "embedding", "indexed", "failed"]
    progress_pct: int
    chunk_count: int
    created_at: datetime
