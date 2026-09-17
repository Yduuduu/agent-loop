from app.db.session import Base  # noqa: F401

# 모델 클래스(Order, OrderItem, RefundCase, RefundDecision, PolicyDocument 등)는
# Phase 1에서 추가된다. 이 모듈은 alembic/env.py가 import하므로 모델이 생기는 즉시
# Base.metadata를 통해 autogenerate가 인식할 수 있다.
