"""Emergency fix: Add missing columns with raw SQL

Revision ID: m1n2o3p4q5r6
Revises: l6m7n8o9p0q1
Create Date: 2026-01-06 15:00:00.000000

This migration adds all potentially missing columns using raw SQL
with IF NOT EXISTS checks. Runs at the END of the migration chain
to ensure all columns exist regardless of previous migration state.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm1n2o3p4q5r6'
down_revision = 'l6m7n8o9p0q1'
branch_labels = None
depends_on = None


def upgrade():
    """Add all potentially missing columns using PostgreSQL raw SQL."""
    conn = op.get_bind()

    # Members table - Shopify subscription columns
    columns_to_add = [
        ("members", "shopify_subscription_contract_id", "VARCHAR(100)"),
        ("members", "subscription_status", "VARCHAR(20) DEFAULT 'none'"),
        ("members", "tier_assigned_by", "VARCHAR(100)"),
        ("members", "tier_assigned_at", "TIMESTAMP"),
        ("members", "tier_expires_at", "TIMESTAMP"),
        ("members", "shopify_customer_gid", "VARCHAR(100)"),
        ("members", "partner_customer_id", "VARCHAR(100)"),
        # Membership tiers
        ("membership_tiers", "shopify_selling_plan_id", "VARCHAR(100)"),
        ("membership_tiers", "yearly_price", "NUMERIC(10,2)"),
    ]

    for table, column, col_type in columns_to_add:
        # Check if column exists
        result = conn.execute(sa.text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
        """), {'table_name': table, 'column_name': column})

        if not result.scalar():
            print(f"[Migration] Adding missing column: {table}.{column}")
            conn.execute(sa.text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
        else:
            print(f"[Migration] Column already exists: {table}.{column}")


def downgrade():
    """No downgrade - this is an emergency fix migration."""
    pass
