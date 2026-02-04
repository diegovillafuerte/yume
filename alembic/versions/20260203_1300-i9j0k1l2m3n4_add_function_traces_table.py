"""add function_traces table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('function_traces',
        sa.Column('correlation_id', sa.UUID(), nullable=False),
        sa.Column('parent_trace_id', sa.UUID(), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('function_name', sa.String(length=255), nullable=False),
        sa.Column('module_path', sa.String(length=255), nullable=False),
        sa.Column('trace_type', sa.String(length=50), nullable=False),
        sa.Column('input_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=50), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('is_error', sa.Boolean(), nullable=False),
        sa.Column('error_type', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    # Composite index for ordering traces within a correlation
    op.create_index('ix_func_trace_corr_seq', 'function_traces', ['correlation_id', 'sequence_number'], unique=False)
    # Index for listing by creation time (descending for recent-first)
    op.create_index('ix_func_trace_created', 'function_traces', ['created_at'], unique=False)
    # Index for filtering by phone number
    op.create_index('ix_func_trace_phone', 'function_traces', ['phone_number'], unique=False)
    # Index for filtering by organization
    op.create_index('ix_func_trace_org', 'function_traces', ['organization_id'], unique=False)
    # Index for filtering by error status
    op.create_index('ix_func_trace_error', 'function_traces', ['is_error'], unique=False)
    # Index for correlation_id alone (for lookups)
    op.create_index('ix_function_traces_correlation_id', 'function_traces', ['correlation_id'], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('ix_function_traces_correlation_id', table_name='function_traces')
    op.drop_index('ix_func_trace_error', table_name='function_traces')
    op.drop_index('ix_func_trace_org', table_name='function_traces')
    op.drop_index('ix_func_trace_phone', table_name='function_traces')
    op.drop_index('ix_func_trace_created', table_name='function_traces')
    op.drop_index('ix_func_trace_corr_seq', table_name='function_traces')
    op.drop_table('function_traces')
