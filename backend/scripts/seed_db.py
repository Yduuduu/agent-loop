"""backend/data/mock_orders.json으로 로컬 DB를 시딩한다.

Phase 0: 아직 ORM 모델이 없어 픽스처 형식 검증만 수행한다.
Phase 1에서 SQLAlchemy 모델(Order, OrderItem, ...)이 추가되면
이 스크립트도 async 세션으로 실제 row를 insert하도록 확장된다.
"""

import asyncio
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_orders.json"
REQUIRED_ORDER_FIELDS = {
    "order_id",
    "scenario",
    "customer_email",
    "purchased_at",
    "return_window_days",
    "items",
    "refund_request",
    "expected_decision",
}


def load_orders() -> list[dict]:
    payload = json.loads(DATA_PATH.read_text())
    orders = payload["orders"]
    for order in orders:
        missing = REQUIRED_ORDER_FIELDS - order.keys()
        if missing:
            raise ValueError(f"{order.get('order_id', '?')} missing fields: {missing}")
    return orders


async def seed() -> None:
    orders = load_orders()
    print(f"loaded {len(orders)} mock orders from {DATA_PATH}")
    for order in orders:
        print(f"  - {order['order_id']}: {order['scenario_description']}")
    print("TODO(Phase 1): insert into Order/OrderItem tables via async session")


if __name__ == "__main__":
    asyncio.run(seed())
