from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from langchain_chroma import Chroma
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.refund_agent.graph import build_graph
from app.db.session import get_session
from app.rag.retriever import get_vectorstore

SessionDep = Annotated[AsyncSession, Depends(get_session)]

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
