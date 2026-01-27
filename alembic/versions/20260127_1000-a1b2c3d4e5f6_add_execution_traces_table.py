"""add execution_traces table

Revision ID: a1b2c3d4e5f6
Revises: 9e06fdca4153
Create Date: 2026-01-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9e06fdca4153'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('execution_traces',
        sa.Column('exchange_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=True),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('trace_type', sa.String(length=50), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_error', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Index for grouping traces by exchange
    op.create_index('ix_execution_traces_exchange_id', 'execution_traces', ['exchange_id'], unique=False)
    # Composite index for listing traces by org and creation time
    op.create_index('ix_execution_traces_org_created', 'execution_traces', ['organization_id', 'created_at'], unique=False)
    # Index for filtering by conversation
    op.create_index('ix_execution_traces_conversation_id', 'execution_traces', ['conversation_id'], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('ix_execution_traces_conversation_id', table_name='execution_traces')
    op.drop_index('ix_execution_traces_org_created', table_name='execution_traces')
    op.drop_index('ix_execution_traces_exchange_id', table_name='execution_traces')
    op.drop_table('execution_traces')
