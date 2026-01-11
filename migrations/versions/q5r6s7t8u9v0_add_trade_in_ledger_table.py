"""Add trade_in_ledger table for simplified trade-in tracking.

Revision ID: q5r6s7t8u9v0
Revises: p4q5r6s7t8u9
Create Date: 2026-01-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'q5r6s7t8u9v0'
down_revision = 'p4q5r6s7t8u9'
branch_labels = None
depends_on = None


def upgrade():
    """Create trade_in_ledger table."""
    op.create_table(
        'trade_in_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('guest_name', sa.String(200), nullable=True),
        sa.Column('guest_email', sa.String(200), nullable=True),
        sa.Column('guest_phone', sa.String(50), nullable=True),
        sa.Column('reference', sa.String(50), nullable=False),
        sa.Column('trade_date', sa.DateTime(), nullable=False),
        sa.Column('total_value', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('cash_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('credit_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('collection_id', sa.String(100), nullable=True),
        sa.Column('collection_name', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference')
    )

    # Create indexes
    op.create_index('ix_trade_ledger_tenant_id', 'trade_in_ledger', ['tenant_id'])
    op.create_index('ix_trade_ledger_member_id', 'trade_in_ledger', ['member_id'])
    op.create_index('ix_trade_ledger_tenant_date', 'trade_in_ledger', ['tenant_id', 'trade_date'])
    op.create_index('ix_trade_ledger_tenant_category', 'trade_in_ledger', ['tenant_id', 'category'])


def downgrade():
    """Drop trade_in_ledger table."""
    op.drop_index('ix_trade_ledger_tenant_category', 'trade_in_ledger')
    op.drop_index('ix_trade_ledger_tenant_date', 'trade_in_ledger')
    op.drop_index('ix_trade_ledger_member_id', 'trade_in_ledger')
    op.drop_index('ix_trade_ledger_tenant_id', 'trade_in_ledger')
    op.drop_table('trade_in_ledger')
