import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from langchain_chroma import Chroma
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.refund_agent.graph import build_graph
from app.core.config import get_settings
from app.db.session import get_session
from app.rag.policy_summarizer import SummarizeFn, default_summarize_policy_document
from app.rag.retriever import get_vectorstore

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_admin_security = HTTPBasic()
AdminCredentialsDep = Annotated[HTTPBasicCredentials, Depends(_admin_security)]

# HTTP Basic 인증정보는 브라우저가 origin 단위로 캐시해뒀다가, 그 origin으로
# 가는 "모든" 요청에 자동으로 재첨부한다 — 쿠키와 마찬가지로 CSRF에 취약하다는
# 뜻이다. 상태를 바꾸는 요청(POST/PUT/PATCH/DELETE)에 한해 일반 HTML <form>이
# 절대 보낼 수 없는 커스텀 헤더를 요구해, 이 헤더가 없으면(= 브라우저가 그
# 요청을 cross-origin 사전요청(preflight) 없이 보냈다는 뜻) 차단한다. 이
# 헤더가 붙으면 브라우저는 반드시 CORS 프리플라이트를 먼저 보내고, 그 단계는
# main.py의 origin 허용목록이 이미 검증한다.
CSRF_HEADER_NAME = "X-Requested-With"
CSRF_HEADER_VALUE = "XMLHttpRequest"
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def require_admin_auth(request: Request, credentials: AdminCredentialsDep) -> None:
    """관리자 라우터(환불 케이스, 지식베이스) 앞단의 HTTP Basic 인증 + CSRF 게이트.

    Phase 6.2: 1인 관리자 도구라 세션/JWT 대신 가장 단순한 방식을 택했다 —
    브라우저가 네이티브 로그인 창을 띄워주므로 별도 로그인 페이지가 필요 없다.
    ADMIN_USERNAME/ADMIN_PASSWORD가 비어 있으면(미설정) 기본값으로 열어주는
    대신 fail-closed로 전부 500 처리한다 — 배포 시 설정을 빠뜨렸을 때
    "인증 없이 열려 있는" 상태보다 "아예 안 되는" 상태가 훨씬 안전하다.
    """
    settings = get_settings()
    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="관리자 인증이 설정되지 않았습니다 (ADMIN_USERNAME/ADMIN_PASSWORD)",
        )

    valid_username = secrets.compare_digest(credentials.username, settings.admin_username)
    valid_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 실패",
            headers={"WWW-Authenticate": "Basic"},
        )

    if (
        request.method in _MUTATING_METHODS
        and request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF 방지 헤더가 없는 요청입니다",
        )


AdminAuthDep = Annotated[None, Depends(require_admin_auth)]

# 테스트에서 app.dependency_overrides[get_graph_builder]로 치환해
# 실제 LLM 호출 없이 fake 콜러블이 주입된 그래프를 사용하게 한다.
# checkpointer는 케이스마다가 아니라 호출 시점(refund_runner)에 열고 닫는
# 연결이므로 여기서는 "체크포인터를 받아 그래프를 만드는 함수"만 제공한다.
GraphBuilder = Callable[[BaseCheckpointSaver], CompiledStateGraph]


def get_graph_builder() -> GraphBuilder:
    return lambda checkpointer: build_graph(checkpointer=checkpointer)


GraphBuilderDep = Annotated[GraphBuilder, Depends(get_graph_builder)]

# 테스트에서 app.dependency_overrides[get_vectorstore_builder]로 치환해
# 실제 임베딩 API 호출 없이 fake 벡터스토어(임시 디렉터리 + 결정론적 임베딩)를 쓴다.
VectorstoreBuilder = Callable[[], Chroma]


def get_vectorstore_builder() -> VectorstoreBuilder:
    return get_vectorstore


VectorstoreBuilderDep = Annotated[VectorstoreBuilder, Depends(get_vectorstore_builder)]

# 테스트에서 app.dependency_overrides[get_policy_summarizer]로 치환해
# 실제 LLM 호출 없이 결정론적인 fake 요약 함수를 쓴다.


def get_policy_summarizer() -> SummarizeFn:
    return default_summarize_policy_document


PolicySummarizerDep = Annotated[SummarizeFn, Depends(get_policy_summarizer)]
