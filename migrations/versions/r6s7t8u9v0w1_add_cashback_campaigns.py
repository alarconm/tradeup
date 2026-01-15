"""Add cashback campaigns tables.

Revision ID: r6s7t8u9v0w1
Revises: q5r6s7t8u9v0
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r6s7t8u9v0w1'
down_revision = 'q5r6s7t8u9v0'
branch_labels = None
depends_on = None


def upgrade():
    """Create cashback_campaigns and cashback_redemptions tables."""
    # Cashback Campaigns table
    op.create_table(
        'cashback_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('cashback_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('min_purchase', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_cashback', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_total_cashback', sa.Numeric(12, 2), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('applies_to', sa.String(50), server_default='all'),
        sa.Column('tier_restriction', sa.Text(), nullable=True),
        sa.Column('included_products', sa.Text(), nullable=True),
        sa.Column('excluded_products', sa.Text(), nullable=True),
        sa.Column('applies_to_new_customers', sa.Boolean(), server_default='true'),
        sa.Column('applies_to_existing_customers', sa.Boolean(), server_default='true'),
        sa.Column('stackable_with_discounts', sa.Boolean(), server_default='true'),
        sa.Column('stackable_with_promotions', sa.Boolean(), server_default='true'),
        sa.Column('max_uses_total', sa.Integer(), nullable=True),
        sa.Column('max_uses_per_customer', sa.Integer(), server_default='1'),
        sa.Column('current_uses', sa.Integer(), server_default='0'),
        sa.Column('total_cashback_issued', sa.Numeric(12, 2), server_default='0'),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_cashback_campaigns_tenant_id', 'cashback_campaigns', ['tenant_id'])
    op.create_index('ix_cashback_campaigns_status', 'cashback_campaigns', ['status'])
    op.create_index('ix_cashback_campaigns_dates', 'cashback_campaigns', ['start_date', 'end_date'])

    # Cashback Redemptions table
    op.create_table(
        'cashback_redemptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('shopify_order_id', sa.String(100), nullable=False),
        sa.Column('order_number', sa.String(50), nullable=True),
        sa.Column('order_total', sa.Numeric(10, 2), nullable=False),
        sa.Column('cashback_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('cashback_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('credit_issued', sa.Boolean(), server_default='false'),
        sa.Column('credit_entry_id', sa.Integer(), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_tier', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['cashback_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_cashback_redemptions_tenant_id', 'cashback_redemptions', ['tenant_id'])
    op.create_index('ix_cashback_redemptions_campaign_id', 'cashback_redemptions', ['campaign_id'])
    op.create_index('ix_cashback_redemptions_member_id', 'cashback_redemptions', ['member_id'])
    op.create_index('ix_cashback_redemptions_order_id', 'cashback_redemptions', ['shopify_order_id'])


def downgrade():
    """Drop cashback tables."""
    op.drop_table('cashback_redemptions')
    op.drop_table('cashback_campaigns')
