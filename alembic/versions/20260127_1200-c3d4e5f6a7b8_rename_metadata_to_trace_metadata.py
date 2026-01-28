"""rename metadata to trace_metadata

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename metadata column to trace_metadata to avoid SQLAlchemy reserved name."""
    op.alter_column(
        'execution_traces',
        'metadata',
        new_column_name='trace_metadata'
    )


def downgrade() -> None:
    """Rename trace_metadata back to metadata."""
    op.alter_column(
        'execution_traces',
        'trace_metadata',
        new_column_name='metadata'
    )
