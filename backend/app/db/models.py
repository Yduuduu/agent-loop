from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid_hex() -> str:
    return uuid.uuid4().hex


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_email: Mapped[str] = mapped_column(String(255))
    purchased_at: Mapped[date] = mapped_column(Date)
    return_window_days: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    item_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    unit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class RefundCase(Base):
    __tablename__ = "refund_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Phase 3에서 case_id == LangGraph thread_id 규약으로 재사용된다.
    case_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=_uuid_hex)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    user_message: Mapped[str] = mapped_column(Text)
    image_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # Phase 3 HITL 대기열용 필드 (Phase 1에서는 미사용, 스키마만 선점)
    flagged_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    awaiting_human_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    decision: Mapped[RefundDecision | None] = relationship(
        back_populates="case", uselist=False, cascade="all, delete-orphan"
    )


class RefundDecision(Base):
    __tablename__ = "refund_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("refund_cases.case_id"), unique=True)
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    # RefundAgentState 고정 계약에 confidence가 없어 그래프 밖으로 전달되지 않는다.
    # LLM 판정 confidence를 상태에 실어 보내는 것은 향후 phase 과제로 남겨둔다.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_human: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped[RefundCase] = relationship(back_populates="decision")


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=_uuid_hex)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
