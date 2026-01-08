"""Add guest fields to trade_in_batches

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-01-08 09:00:00.000000

Adds guest_name, guest_email, guest_phone columns for non-member trade-ins.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o3p4q5r6s7t8'
down_revision = 'n2o3p4q5r6s7'
branch_labels = None
depends_on = None


def upgrade():
    """Add guest fields to trade_in_batches using safe column checks."""
    conn = op.get_bind()

    columns_to_add = [
        ("trade_in_batches", "guest_name", "VARCHAR(200)"),
        ("trade_in_batches", "guest_email", "VARCHAR(200)"),
        ("trade_in_batches", "guest_phone", "VARCHAR(50)"),
    ]

    for table, column, col_type in columns_to_add:
        # Check if column exists (PostgreSQL)
        result = conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
        """), {'table_name': table, 'column_name': column})

        if not result.scalar():
            print(f"[Migration] Adding column: {table}.{column}")
            conn.execute(sa.text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
        else:
            print(f"[Migration] Column already exists: {table}.{column}")


def downgrade():
    """Remove guest fields from trade_in_batches."""
    op.drop_column('trade_in_batches', 'guest_phone')
    op.drop_column('trade_in_batches', 'guest_email')
    op.drop_column('trade_in_batches', 'guest_name')
