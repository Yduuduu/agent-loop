"""backend/data/mock_orders.json으로 로컬 DB를 시딩한다.

Order/OrderItem 테이블에 5개 시나리오(6개 주문)를 upsert한다.
실행 전 `alembic upgrade head`로 스키마가 준비되어 있어야 한다.
"""

import asyncio
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.db.models import Order, OrderItem
from app.db.session import async_session_factory

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

    async with async_session_factory() as session:
        for payload in orders:
            existing = await session.scalar(
                select(Order).where(Order.order_id == payload["order_id"])
            )
            if existing is not None:
                print(f"  - {payload['order_id']}: already seeded, skipping")
                continue

            order = Order(
                order_id=payload["order_id"],
                customer_email=payload["customer_email"],
                purchased_at=date.fromisoformat(payload["purchased_at"]),
                return_window_days=payload["return_window_days"],
            )
            order.items = [
                OrderItem(
                    item_id=item["item_id"],
                    sku=item["sku"],
                    name=item["name"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                )
                for item in payload["items"]
            ]
            session.add(order)
            print(f"  - {payload['order_id']}: {payload['scenario_description']}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
