"""Add promotions and store credit tables

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-01-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f0a1b2c3d4'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade():
    # Create promotions table
    op.create_table('promotions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('promo_type', sa.String(length=30), nullable=False, server_default='trade_in_bonus'),
        sa.Column('bonus_percent', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('bonus_flat', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('multiplier', sa.Numeric(precision=4, scale=2), nullable=True, server_default='1.0'),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('daily_start_time', sa.Time(), nullable=True),
        sa.Column('daily_end_time', sa.Time(), nullable=True),
        sa.Column('active_days', sa.String(length=20), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=True, server_default='all'),
        sa.Column('category_ids', sa.Text(), nullable=True),
        sa.Column('tier_restrictions', sa.String(length=100), nullable=True),
        sa.Column('min_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('max_bonus', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('min_items', sa.Integer(), nullable=True),
        sa.Column('stackable', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('current_uses', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_promotions_code'), 'promotions', ['code'], unique=True)

    # Create store_credit_ledger table
    op.create_table('store_credit_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('balance_after', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=True),
        sa.Column('source_id', sa.String(length=100), nullable=True),
        sa.Column('source_reference', sa.String(length=200), nullable=True),
        sa.Column('promotion_id', sa.Integer(), nullable=True),
        sa.Column('promotion_name', sa.String(length=100), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=True),
        sa.Column('synced_to_shopify', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('shopify_credit_id', sa.String(length=100), nullable=True),
        sa.Column('sync_error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True, server_default='system'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
        sa.ForeignKeyConstraint(['promotion_id'], ['promotions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_store_credit_ledger_member_id'), 'store_credit_ledger', ['member_id'], unique=False)
    op.create_index(op.f('ix_store_credit_ledger_source_id'), 'store_credit_ledger', ['source_id'], unique=False)

    # Create member_credit_balances table
    op.create_table('member_credit_balances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('total_balance', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('available_balance', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('pending_balance', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('total_earned', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('total_spent', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('trade_in_earned', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('cashback_earned', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('promo_bonus_earned', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('last_credit_at', sa.DateTime(), nullable=True),
        sa.Column('last_redemption_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('member_id')
    )

    # Create bulk_credit_operations table
    op.create_table('bulk_credit_operations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('amount_per_member', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('tier_filter', sa.String(length=100), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create tier_configurations table
    op.create_table('tier_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tier_name', sa.String(length=20), nullable=False),
        sa.Column('monthly_price', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('trade_in_bonus_pct', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('purchase_cashback_pct', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('store_discount_pct', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('quick_flip_days', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('early_access_days', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('color', sa.String(length=30), nullable=True, server_default='slate'),
        sa.Column('badge_text', sa.String(length=30), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tier_name')
    )


def downgrade():
    op.drop_table('tier_configurations')
    op.drop_table('bulk_credit_operations')
    op.drop_table('member_credit_balances')
    op.drop_index(op.f('ix_store_credit_ledger_source_id'), table_name='store_credit_ledger')
    op.drop_index(op.f('ix_store_credit_ledger_member_id'), table_name='store_credit_ledger')
    op.drop_table('store_credit_ledger')
    op.drop_index(op.f('ix_promotions_code'), table_name='promotions')
    op.drop_table('promotions')
