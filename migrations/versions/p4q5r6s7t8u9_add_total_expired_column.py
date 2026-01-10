"""Add total_expired column to member_credit_balances

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-01-10

"""
from alembic import op
import sqlalchemy as sa


revision = 'p4q5r6s7t8u9'
down_revision = 'o3p4q5r6s7t8'
branch_labels = None
depends_on = None


def column_exists(conn, table_name, column_name):
    """Check if a column exists in a table."""
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
        )
    """), {'table_name': table_name, 'column_name': column_name})
    return result.scalar()


def upgrade():
    conn = op.get_bind()

    # Add total_expired column to member_credit_balances if it doesn't exist
    if not column_exists(conn, 'member_credit_balances', 'total_expired'):
        op.add_column('member_credit_balances',
            sa.Column('total_expired', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0')
        )


def downgrade():
    op.drop_column('member_credit_balances', 'total_expired')
