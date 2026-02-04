"""add customer_flow_sessions table

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-03 11:00:00.000000

Creates the customer_flow_sessions table for tracking customer conversation flows
(booking, modify, cancel, rating). This implements Phase 4 of the Message Routing
Architecture - End Customer Flow State Machines.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create customer_flow_sessions table."""
    op.create_table(
        'customer_flow_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('end_customer_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('flow_type', sa.String(20), nullable=False, server_default='inquiry'),
        sa.Column('state', sa.String(50), nullable=False, server_default='initiated'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('collected_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['end_customer_id'], ['end_customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('ix_customer_flow_conversation_id', 'customer_flow_sessions', ['conversation_id'])
    op.create_index('ix_customer_flow_end_customer_id', 'customer_flow_sessions', ['end_customer_id'])
    op.create_index('ix_customer_flow_organization_id', 'customer_flow_sessions', ['organization_id'])
    # Index for finding active flows (common query pattern)
    op.create_index('ix_customer_flow_active', 'customer_flow_sessions', ['conversation_id', 'is_active'])


def downgrade() -> None:
    """Drop customer_flow_sessions table."""
    op.drop_index('ix_customer_flow_active', table_name='customer_flow_sessions')
    op.drop_index('ix_customer_flow_organization_id', table_name='customer_flow_sessions')
    op.drop_index('ix_customer_flow_end_customer_id', table_name='customer_flow_sessions')
    op.drop_index('ix_customer_flow_conversation_id', table_name='customer_flow_sessions')
    op.drop_table('customer_flow_sessions')
