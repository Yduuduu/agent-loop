"""id별 SSE 이벤트를 담는 인프로세스 큐 레지스트리.

Phase 2는 단일 프로세스/단일 클라이언트를 가정한 단순 구현이다.
Pub/Sub이나 재연결 시 이벤트 재생은 다루지 않는다 — 스트리밍 연결과
그래프 실행을 분리하는 것은 Phase 3(pause/resume)의 과제로 남겨둔다.

refund case(Phase 2/3)와 지식베이스 문서(Phase 6)가 이 레지스트리를 함께
쓴다 — `.to_wire()`만 있으면 이벤트 타입은 상관없다. 두 도메인의 id
네임스페이스가 우연히 겹치지 않도록 호출자가 키를 접두어로 구분한다
(예: refund_runner는 case_id 그대로, kb_runner는 "kb:{doc_id}").
"""

import asyncio
from typing import Protocol

# 각 큐의 종료를 알리는 sentinel
STREAM_DONE = object()

_queues: dict[str, asyncio.Queue] = {}


class WireEvent(Protocol):
    def to_wire(self) -> str: ...


def create_queue(key: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues[key] = queue
    return queue


def get_queue(key: str) -> asyncio.Queue | None:
    return _queues.get(key)


async def publish(key: str, event: WireEvent) -> None:
    queue = _queues.get(key)
    if queue is not None:
        await queue.put(event)


async def publish_done(key: str) -> None:
    queue = _queues.get(key)
    if queue is not None:
        await queue.put(STREAM_DONE)


def remove_queue(key: str) -> None:
    _queues.pop(key, None)
