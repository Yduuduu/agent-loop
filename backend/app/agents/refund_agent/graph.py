from datetime import date

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.refund_agent.nodes import (
    AssessDamageFn,
    DecideFn,
    NowFn,
    OrderLookupFn,
    SearchPolicyFn,
    default_assess_damage,
    default_decide,
    default_order_lookup,
    default_search_policy,
    finalize_node,
    flag_for_human_node,
    make_damage_assessment_node,
    make_decision_node,
    make_order_lookup_node,
    make_policy_rag_search_node,
    route_after_decision,
)
from app.agents.refund_agent.state import RefundAgentState


def build_graph(
    *,
    order_lookup: OrderLookupFn = default_order_lookup,
    assess_damage: AssessDamageFn = default_assess_damage,
    search_policy: SearchPolicyFn = default_search_policy,
    decide: DecideFn = default_decide,
    now_fn: NowFn = date.today,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """RefundAgent StateGraph를 조립한다.

    기본값은 실제 DB/LLM/RAG를 호출하는 구현이며, 테스트에서는 각 인자에
    결정론적인 fake 콜러블을 주입해 네트워크 호출 없이 그래프 로직을 검증한다.

    flag_for_human 노드가 interrupt()로 실행을 진짜 중단하므로 체크포인터가
    항상 필요하다 — checkpointer를 넘기지 않으면 프로세스 재시작에도 살아남지
    못하는 InMemorySaver를 기본값으로 쓴다(CLI/테스트 등 1회성 실행용).
    실제 API는 AsyncSqliteSaver를 명시적으로 넘겨 재개 가능하게 한다.
    """
    graph = StateGraph(RefundAgentState)

    graph.add_node("order_lookup", make_order_lookup_node(order_lookup))
    graph.add_node("damage_assessment", make_damage_assessment_node(assess_damage))
    graph.add_node("policy_rag_search", make_policy_rag_search_node(search_policy))
    graph.add_node("decision", make_decision_node(decide, now_fn))
    graph.add_node("finalize", finalize_node)
    graph.add_node("flag_for_human", flag_for_human_node)

    graph.add_edge(START, "order_lookup")
    graph.add_edge("order_lookup", "damage_assessment")
    graph.add_edge("damage_assessment", "policy_rag_search")
    graph.add_edge("policy_rag_search", "decision")
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"finalize": "finalize", "flag_for_human": "flag_for_human"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("flag_for_human", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
