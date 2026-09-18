"""케이스별 SSE 이벤트를 담는 인프로세스 큐 레지스트리.

Phase 2는 단일 프로세스/단일 클라이언트를 가정한 단순 구현이다.
Pub/Sub이나 재연결 시 이벤트 재생은 다루지 않는다 — 스트리밍 연결과
그래프 실행을 분리하는 것은 Phase 3(pause/resume)의 과제로 남겨둔다.
"""

import asyncio

from app.api.schemas.sse_events import SSEEvent

# 각 큐의 종료를 알리는 sentinel
STREAM_DONE = object()

_queues: dict[str, asyncio.Queue] = {}


def create_queue(case_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _queues[case_id] = queue
    return queue


def get_queue(case_id: str) -> asyncio.Queue | None:
    return _queues.get(case_id)


async def publish(case_id: str, event: SSEEvent) -> None:
    queue = _queues.get(case_id)
    if queue is not None:
        await queue.put(event)


async def publish_done(case_id: str) -> None:
    queue = _queues.get(case_id)
    if queue is not None:
        await queue.put(STREAM_DONE)


def remove_queue(case_id: str) -> None:
    _queues.pop(case_id, None)
