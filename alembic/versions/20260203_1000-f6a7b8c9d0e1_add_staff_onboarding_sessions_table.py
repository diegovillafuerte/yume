"""add staff_onboarding_sessions table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-03 10:00:00.000000

Creates the staff_onboarding_sessions table for tracking staff onboarding
via WhatsApp. This is triggered when a pre-registered staff member sends
their first message to the business WhatsApp number.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create staff_onboarding_sessions table."""
    op.create_table(
        'staff_onboarding_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('staff_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('state', sa.String(50), nullable=False, server_default='initiated'),
        sa.Column('collected_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('conversation_context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['staff_id'], ['yume_users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('staff_id', name='uq_staff_onboarding_staff_id'),
    )

    # Create indexes
    op.create_index('ix_staff_onboarding_staff_id', 'staff_onboarding_sessions', ['staff_id'])
    op.create_index('ix_staff_onboarding_organization_id', 'staff_onboarding_sessions', ['organization_id'])


def downgrade() -> None:
    """Drop staff_onboarding_sessions table."""
    op.drop_index('ix_staff_onboarding_organization_id', table_name='staff_onboarding_sessions')
    op.drop_index('ix_staff_onboarding_staff_id', table_name='staff_onboarding_sessions')
    op.drop_table('staff_onboarding_sessions')
