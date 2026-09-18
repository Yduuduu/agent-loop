"""지식베이스 인제스천 SSE 이벤트 스키마 — Phase 2의 SSEEvent와 동일한 패턴
(event/data 두 줄 형식)을 재사용하되, refund 케이스와는 독립된 이벤트 타입을 쓴다.
"""

import json
from enum import StrEnum

from pydantic import BaseModel


class KBEventType(StrEnum):
    UPLOADED = "uploaded"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


class KBEvent(BaseModel):
    event: KBEventType
    doc_id: str
    data: dict

    def to_wire(self) -> str:
        payload = {"doc_id": self.doc_id, **self.data}
        return f"event: {self.event.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
