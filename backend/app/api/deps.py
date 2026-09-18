from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.refund_agent.graph import build_graph
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# 테스트에서 app.dependency_overrides[get_graph_builder]로 치환해
# 실제 LLM 호출 없이 fake 콜러블이 주입된 그래프를 사용하게 한다.
GraphBuilder = Callable[[], CompiledStateGraph]


def get_graph_builder() -> GraphBuilder:
    return build_graph


GraphBuilderDep = Annotated[GraphBuilder, Depends(get_graph_builder)]
