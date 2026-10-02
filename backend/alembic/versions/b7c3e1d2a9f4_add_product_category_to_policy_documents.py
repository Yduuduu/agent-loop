"""add product_category to policy_documents

Revision ID: b7c3e1d2a9f4
Revises: f8a972d6a5a8
Create Date: 2026-10-01 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c3e1d2a9f4"
down_revision: Union[str, Sequence[str], None] = "f8a972d6a5a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 체크포인터 소유 테이블(checkpoints/writes)은 건드리지 않는다 — 이전 마이그레이션 참고.
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("product_category", sa.String(length=64), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_policy_documents_product_category"), ["product_category"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_policy_documents_product_category"))
        batch_op.drop_column("product_category")
