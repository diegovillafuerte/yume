"""rename onboarding state started to initiated

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-03 09:30:00.000000

Renames the onboarding session state from 'started' to 'initiated' for
consistency with the docs/PROJECT_SPEC.md document.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename state 'started' to 'initiated' in onboarding_sessions."""
    op.execute("""
        UPDATE onboarding_sessions
        SET state = 'initiated'
        WHERE state = 'started'
    """)


def downgrade() -> None:
    """Rename state 'initiated' back to 'started' in onboarding_sessions."""
    op.execute("""
        UPDATE onboarding_sessions
        SET state = 'started'
        WHERE state = 'initiated'
    """)
