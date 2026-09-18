"""add progress_pct to policy_documents

Revision ID: 53aa9d951a6b
Revises: 5fdb0edf10cb
Create Date: 2026-09-18 12:12:15.279488

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "53aa9d951a6b"
down_revision: Union[str, Sequence[str], None] = "5fdb0edf10cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate도 'checkpoints'/'writes' 테이블을 drop하자고 제안했지만
    # 이건 우리 SQLAlchemy 모델이 아니라 LangGraph AsyncSqliteSaver 체크포인터가
    # 같은 SQLite 파일에 관리하는 테이블이다(Phase 3). Base.metadata에 없다고
    # autogenerate가 삭제 대상으로 착각한 것 — 그대로 적용하면 저장된 HITL
    # 체크포인트가 전부 날아간다. 의도한 변경(progress_pct 추가)만 남겼다.
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policy_documents", schema=None) as batch_op:
        batch_op.drop_column("progress_pct")
