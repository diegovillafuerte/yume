"""add first_message_at and permission_level to yume_users

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-03 09:00:00.000000

Adds:
- first_message_at: timestamp for first WhatsApp message (NULL = never messaged)
- permission_level: owner/admin/staff/viewer for permission matrix
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add first_message_at and permission_level columns."""
    # Add first_message_at column (nullable, NULL means never messaged)
    op.add_column(
        'yume_users',
        sa.Column('first_message_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add permission_level column with default 'staff'
    op.add_column(
        'yume_users',
        sa.Column('permission_level', sa.String(20), nullable=False, server_default='staff')
    )

    # Set permission_level='owner' for users with role='owner'
    op.execute("""
        UPDATE yume_users
        SET permission_level = 'owner'
        WHERE role = 'owner'
    """)


def downgrade() -> None:
    """Remove first_message_at and permission_level columns."""
    op.drop_column('yume_users', 'permission_level')
    op.drop_column('yume_users', 'first_message_at')
