"""add end_customer profile fields

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-03 12:00:00.000000

Adds profile fields to end_customers table for returning customer experience:
- name_verified_at: When customer confirmed their name
- profile_data: JSONB for extended profile (preferences, history summary)

These fields support cross-business customer lookup and personalized experiences.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile fields to end_customers table."""
    # Add name_verified_at column
    op.add_column(
        'end_customers',
        sa.Column('name_verified_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add profile_data column with default empty object
    op.add_column(
        'end_customers',
        sa.Column(
            'profile_data',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}'
        )
    )


def downgrade() -> None:
    """Remove profile fields from end_customers table."""
    op.drop_column('end_customers', 'profile_data')
    op.drop_column('end_customers', 'name_verified_at')
