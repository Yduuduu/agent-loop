import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agents.refund_agent.state import initial_state
from app.api import event_bus
from app.api.deps import GraphBuilderDep, SessionDep
from app.api.refund_runner import resume_case, run_case
from app.api.schemas.refund import (
    RefundCaseStatusResponse,
    RefundRequestCreateResponse,
    RefundResumeRequest,
)
from app.core.config import get_settings
from app.db.models import RefundCase, RefundDecision

router = APIRouter(prefix="/api/refund-requests", tags=["refund-requests"])

# fire-and-forget 백그라운드 태스크가 GC되지 않도록 강한 참조를 유지한다.
_background_tasks: set[asyncio.Task] = set()

OrderIdForm = Annotated[str, Form()]
MessageForm = Annotated[str, Form()]
ImagesForm = Annotated[list[UploadFile], File()]


@router.post("", response_model=RefundRequestCreateResponse)
async def create_refund_request(
    session: SessionDep,
    build_graph: GraphBuilderDep,
    order_id: OrderIdForm,
    message: MessageForm,
    images: ImagesForm = [],  # noqa: B006 — FastAPI Form/File 관례, 요청마다 새로 바인딩됨
) -> RefundRequestCreateResponse:
    case = RefundCase(order_id=order_id, user_message=message, image_refs=[], status="pending")
    session.add(case)
    await session.commit()
    await session.refresh(case)

    image_refs = await _save_uploads(case.case_id, images)
    case.image_refs = image_refs
    await session.commit()

    event_bus.create_queue(case.case_id)
    state = initial_state(order_id=order_id, user_message=message, image_refs=image_refs)
    task = asyncio.create_task(run_case(case.case_id, build_graph, state))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return RefundRequestCreateResponse(case_id=case.case_id)


@router.get("", response_model=list[RefundCaseStatusResponse])
async def list_refund_requests(
    session: SessionDep, status: str | None = None
) -> list[RefundCaseStatusResponse]:
    query = select(RefundCase)
    if status is not None:
        query = query.where(RefundCase.status == status)
    query = query.order_by(RefundCase.created_at.desc())

    cases = (await session.scalars(query)).all()
    responses = []
    for case in cases:
        decision = await session.scalar(
            select(RefundDecision).where(RefundDecision.case_id == case.case_id)
        )
        responses.append(_to_status_response(case, decision))
    return responses


@router.post("/{case_id}/resume", response_model=RefundRequestCreateResponse)
async def resume_refund_request(
    case_id: str,
    payload: RefundResumeRequest,
    session: SessionDep,
    build_graph: GraphBuilderDep,
) -> RefundRequestCreateResponse:
    case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    if case.status != "awaiting_human":
        raise HTTPException(
            status_code=409, detail=f"case is not awaiting human review (status={case.status})"
        )

    # 원래 SSE 연결은 이미 끊겼을 수 있으므로, resume은 GET .../stream으로 다시
    # 연결해 이어지는 이벤트를 받을 수 있도록 새 큐를 연다(같은 case_id 재사용).
    event_bus.create_queue(case_id)
    task = asyncio.create_task(resume_case(case_id, build_graph, payload.model_dump()))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return RefundRequestCreateResponse(case_id=case_id)


@router.get("/{case_id}/stream")
async def stream_refund_request(case_id: str, session: SessionDep) -> StreamingResponse:
    case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    queue = event_bus.get_queue(case_id)
    if queue is None:
        raise HTTPException(
            status_code=410, detail="stream unavailable (already consumed or not started)"
        )

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is event_bus.STREAM_DONE:
                    break
                yield item.to_wire()
        finally:
            event_bus.remove_queue(case_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{case_id}", response_model=RefundCaseStatusResponse)
async def get_refund_request(case_id: str, session: SessionDep) -> RefundCaseStatusResponse:
    case = await session.scalar(select(RefundCase).where(RefundCase.case_id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    decision = await session.scalar(select(RefundDecision).where(RefundDecision.case_id == case_id))
    return _to_status_response(case, decision)


def _to_status_response(
    case: RefundCase, decision: RefundDecision | None
) -> RefundCaseStatusResponse:
    return RefundCaseStatusResponse(
        case_id=case.case_id,
        order_id=case.order_id,
        status=case.status,
        # awaiting_human 상태는 interrupt() 한가운데라 RefundDecision이 아직
        # 없으므로(재개 후에야 생김) case.status로도 사람 검토 필요 여부를 판단한다.
        requires_human=case.status == "awaiting_human"
        or (decision.requires_human if decision else False),
        decision=decision.decision if decision else None,
        decision_reason=decision.reason if decision else None,
        flagged_reason=case.flagged_reason,
        refund_amount=case.refund_amount,
        awaiting_human_since=case.awaiting_human_since,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


async def _save_uploads(case_id: str, images: list[UploadFile]) -> list[str]:
    if not images or (len(images) == 1 and not images[0].filename):
        return []

    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / case_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    refs = []
    for image in images:
        if not image.filename:
            continue
        dest = upload_dir / image.filename
        dest.write_bytes(await image.read())
        refs.append(str(dest.relative_to(Path(settings.upload_dir).parent)))

    return refs
