"""add file_path and policy_summary to policy_documents

Revision ID: f8a972d6a5a8
Revises: 53aa9d951a6b
Create Date: 2026-09-18 17:30:27.075027

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a972d6a5a8"
down_revision: Union[str, Sequence[str], None] = "53aa9d951a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate가 'checkpoints'/'writes' 테이블(LangGraph AsyncSqliteSaver
    # 체크포인터 소유, Base.metadata 밖)을 삭제 대상으로 잘못 제안했다 — 이전
    # 마이그레이션(53aa9d951a6b)과 동일한 이유로 제거했다. 의도한 컬럼 추가만 남김.
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("file_path", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column(
                "policy_summary_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("policy_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.drop_column("policy_summary")
        batch_op.drop_column("policy_summary_status")
        batch_op.drop_column("file_path")
