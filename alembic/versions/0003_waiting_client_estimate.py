"""Add WAITING_CLIENT_ESTIMATE project status (DEC-012).

Revision ID: 0003_waiting_client_estimate
Revises: 0002_entity_history
Create Date: 2026-09-05

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_waiting_client_estimate"
down_revision: Union[str, Sequence[str], None] = "0002_entity_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE project_status ADD VALUE IF NOT EXISTS 'WAITING_CLIENT_ESTIMATE'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value safely; leave the label in place.
    return
