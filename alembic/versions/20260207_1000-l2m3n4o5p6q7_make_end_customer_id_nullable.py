"""Make end_customer_id nullable for onboarding conversations.

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-02-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make end_customer_id nullable so onboarding can use Conversation without EndCustomer."""
    op.alter_column(
        'conversations',
        'end_customer_id',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    """Revert end_customer_id to non-nullable."""
    # Note: This will fail if there are any rows with NULL end_customer_id
    op.alter_column(
        'conversations',
        'end_customer_id',
        existing_type=sa.UUID(),
        nullable=False,
    )
