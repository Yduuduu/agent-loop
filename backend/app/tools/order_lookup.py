from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Order


async def lookup_order(session: AsyncSession, order_id: str) -> dict | None:
    """order_id로 주문 정보(구매일, 상품, 가격, 반품기한)를 조회한다."""
    order = await session.scalar(
        select(Order).options(selectinload(Order.items)).where(Order.order_id == order_id)
    )
    if order is None:
        return None

    return {
        "order_id": order.order_id,
        "customer_email": order.customer_email,
        "purchased_at": order.purchased_at.isoformat(),
        "return_window_days": order.return_window_days,
        "items": [
            {
                "item_id": item.item_id,
                "sku": item.sku,
                "name": item.name,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
            }
            for item in order.items
        ],
        "total_amount": sum(item.unit_price * item.quantity for item in order.items),
    }
