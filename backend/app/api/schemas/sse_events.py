"""SSE 이벤트 스키마 — LangChain/LangGraph 내부 이벤트 형태를 프론트에 직접
노출하지 않기 위한 어댑터 레이어. 필드명은 Phase 4 프론트 매핑의 기반이 되는
고정 계약이므로 변경 시 프론트와 함께 갱신해야 한다.
"""

import json
from enum import StrEnum

from pydantic import BaseModel


class SSEEventType(StrEnum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    ERROR = "error"
    # Phase 3 추가: 그래프가 interrupt()로 진짜 중단됐을 때 발행된다. decision과
    # 달리 이 스트림 레그는 최종 결과 없이 끝난다 — 관리자가 resume해야
    # 이어지는 새 스트림에서 decision/error가 도착한다.
    AWAITING_HUMAN = "awaiting_human"


class SSEEvent(BaseModel):
    event: SSEEventType
    case_id: str
    data: dict

    def to_wire(self) -> str:
        """네이티브 EventSource가 이벤트 타입별로 리스너를 걸 수 있도록
        `event:`/`data:` 두 줄 형식으로 직렬화한다. data 줄은 이벤트 래퍼를
        중첩하지 않고 case_id와 세부 필드를 평탄화한 JSON이다."""
        payload = {"case_id": self.case_id, **self.data}
        return f"event: {self.event.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
