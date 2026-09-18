"""RefundAgent를 API 없이 단독 실행한다.

사용 예:
    python scripts/run_agent_cli.py --order-id ORD-1001 \\
        --message "제품이 파손된 상태로 도착했습니다." \\
        --image mock_evidence/ord-1001-damage-1.jpg

사전 준비: `python scripts/seed_db.py`로 목업 주문 적재,
`python scripts/ingest_policy_docs.py`로 정책 PDF 인덱싱, `.env`에 GOOGLE_API_KEY 설정.
"""

import argparse
import asyncio
import uuid

from app.agents.refund_agent.graph import build_graph
from app.agents.refund_agent.state import initial_state
from app.core.observability import get_langfuse_callback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RefundAgent CLI 실행기")
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--image", action="append", default=[], dest="images")
    return parser.parse_args()


async def run(order_id: str, message: str, images: list[str]) -> None:
    # CLI는 1회성 실행이라 build_graph() 기본값(InMemorySaver)으로 충분하다 —
    # 사람 검토가 필요한 케이스는 일시정지된 채로 이 프로세스와 함께 끝난다.
    # 재개는 API의 POST .../resume 전용이다(Phase 3).
    graph = build_graph()
    state = initial_state(order_id=order_id, user_message=message, image_refs=images)

    callbacks = []
    langfuse_callback = get_langfuse_callback()
    if langfuse_callback is not None:
        callbacks.append(langfuse_callback)

    config = {"configurable": {"thread_id": uuid.uuid4().hex}, "callbacks": callbacks}

    print(f"=== RefundAgent 실행: order_id={order_id} ===\n")
    final_state = state
    async for step in graph.astream(state, config=config, stream_mode="updates"):
        if "__interrupt__" in step:
            reason = step["__interrupt__"][0].value.get("reason")
            print(f"\n⏸ 사람 검토가 필요합니다: {reason}")
            print("   (CLI는 재개를 지원하지 않습니다 — API의 POST .../resume를 사용하세요)")
            return

        for node_name, update in step.items():
            for msg in update.get("messages", []):
                print(f"[{node_name}] {msg}")
            for key in (
                "decision",
                "decision_reason",
                "requires_human",
                "order_data",
                "damage_assessment",
            ):
                if key in update:
                    final_state[key] = update[key]

    print("\n=== 최종 결과 ===")
    print(f"decision:        {final_state.get('decision')}")
    print(f"requires_human:  {final_state.get('requires_human')}")
    print(f"decision_reason: {final_state.get('decision_reason')}")


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.order_id, args.message, args.images))


if __name__ == "__main__":
    main()
