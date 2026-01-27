"""rename customer and staff terminology

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-27 11:00:00.000000

Renames:
- customers table -> end_customers
- staff table -> yume_users
- staff_service_types table -> yume_user_service_types
- Related columns: customer_id -> end_customer_id, staff_id -> yume_user_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema - rename customer/staff terminology."""

    # Step 1: Rename the main tables
    op.rename_table('customers', 'end_customers')
    op.rename_table('staff', 'yume_users')
    op.rename_table('staff_service_types', 'yume_user_service_types')

    # Step 2: Rename indexes on the renamed tables
    # customers -> end_customers indexes
    op.execute('ALTER INDEX ix_customer_phone_number RENAME TO ix_end_customer_phone_number')

    # staff -> yume_users indexes
    op.execute('ALTER INDEX ix_staff_phone_number RENAME TO ix_yume_user_phone_number')

    # Step 3: Rename columns in appointments table
    op.alter_column('appointments', 'customer_id', new_column_name='end_customer_id')
    op.alter_column('appointments', 'staff_id', new_column_name='yume_user_id')

    # Step 4: Rename columns in conversations table
    op.alter_column('conversations', 'customer_id', new_column_name='end_customer_id')

    # Step 5: Rename columns in availability table
    op.alter_column('availability', 'staff_id', new_column_name='yume_user_id')

    # Step 6: Rename column in yume_user_service_types (association table)
    op.alter_column('yume_user_service_types', 'staff_id', new_column_name='yume_user_id')

    # Step 7: Rename constraints
    # customers unique constraint
    op.execute('ALTER TABLE end_customers RENAME CONSTRAINT uq_customer_org_phone TO uq_end_customer_org_phone')

    # staff unique constraint
    op.execute('ALTER TABLE yume_users RENAME CONSTRAINT uq_staff_org_phone TO uq_yume_user_org_phone')


def downgrade() -> None:
    """Downgrade database schema - revert customer/staff terminology."""

    # Step 1: Rename constraints back
    op.execute('ALTER TABLE end_customers RENAME CONSTRAINT uq_end_customer_org_phone TO uq_customer_org_phone')
    op.execute('ALTER TABLE yume_users RENAME CONSTRAINT uq_yume_user_org_phone TO uq_staff_org_phone')

    # Step 2: Rename columns back
    op.alter_column('yume_user_service_types', 'yume_user_id', new_column_name='staff_id')
    op.alter_column('availability', 'yume_user_id', new_column_name='staff_id')
    op.alter_column('conversations', 'end_customer_id', new_column_name='customer_id')
    op.alter_column('appointments', 'yume_user_id', new_column_name='staff_id')
    op.alter_column('appointments', 'end_customer_id', new_column_name='customer_id')

    # Step 3: Rename indexes back
    op.execute('ALTER INDEX ix_yume_user_phone_number RENAME TO ix_staff_phone_number')
    op.execute('ALTER INDEX ix_end_customer_phone_number RENAME TO ix_customer_phone_number')

    # Step 4: Rename tables back
    op.rename_table('yume_user_service_types', 'staff_service_types')
    op.rename_table('yume_users', 'staff')
    op.rename_table('end_customers', 'customers')
