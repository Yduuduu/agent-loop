"""RefundAgent를 API 없이 단독 실행한다.

사용 예:
    python scripts/run_agent_cli.py --order-id ORD-1001 \\
        --message "제품이 파손된 상태로 도착했습니다." \\
        --image mock_evidence/ord-1001-damage-1.jpg

사전 준비: `python scripts/seed_db.py`로 목업 주문 적재,
`python scripts/ingest_policy_docs.py`로 정책 PDF 인덱싱, `.env`에 OPENAI_API_KEY 설정.
"""

import argparse
import asyncio

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
    graph = build_graph()
    state = initial_state(order_id=order_id, user_message=message, image_refs=images)

    callbacks = []
    langfuse_callback = get_langfuse_callback()
    if langfuse_callback is not None:
        callbacks.append(langfuse_callback)

    config = {"callbacks": callbacks} if callbacks else {}

    print(f"=== RefundAgent 실행: order_id={order_id} ===\n")
    final_state = state
    async for step in graph.astream(state, config=config, stream_mode="updates"):
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
