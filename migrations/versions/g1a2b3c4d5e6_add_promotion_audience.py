"""Add audience field to promotions and guest_credit_events table

Revision ID: g1a2b3c4d5e6
Revises: f0a1b2c3d4e5
Create Date: 2026-01-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1a2b3c4d5e6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add audience column to promotions table and create guest_credit_events table.

    The audience field enables merchants to target:
    - 'members_only' (default) - only enrolled TradeUp members
    - 'all_customers' - any customer who purchases, including non-members

    The guest_credit_events table tracks store credits issued to non-members
    for audit purposes.
    """
    # Add audience column to promotions (existing promos get 'members_only')
    op.add_column('promotions',
        sa.Column('audience', sa.String(50), nullable=False, server_default='members_only')
    )

    # Create guest_credit_events table for audit trail of non-member credits
    op.create_table('guest_credit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('shopify_customer_id', sa.String(100), nullable=False),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('promotion_id', sa.Integer(), nullable=True),
        sa.Column('promotion_name', sa.String(100), nullable=True),
        sa.Column('order_id', sa.String(100), nullable=True),
        sa.Column('order_number', sa.String(50), nullable=True),
        sa.Column('order_total', sa.Numeric(10, 2), nullable=True),
        sa.Column('synced_to_shopify', sa.Boolean(), server_default='false'),
        sa.Column('shopify_credit_id', sa.String(100), nullable=True),
        sa.Column('sync_error', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['promotion_id'], ['promotions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_guest_credit_events_tenant_id', 'guest_credit_events', ['tenant_id'])
    op.create_index('ix_guest_credit_events_shopify_customer_id', 'guest_credit_events', ['shopify_customer_id'])
    op.create_index('ix_guest_credit_events_order_id', 'guest_credit_events', ['order_id'])
    op.create_index('ix_guest_credit_events_created_at', 'guest_credit_events', ['created_at'])


def downgrade():
    """Remove audience column and guest_credit_events table."""
    # Drop indexes
    op.drop_index('ix_guest_credit_events_created_at', table_name='guest_credit_events')
    op.drop_index('ix_guest_credit_events_order_id', table_name='guest_credit_events')
    op.drop_index('ix_guest_credit_events_shopify_customer_id', table_name='guest_credit_events')
    op.drop_index('ix_guest_credit_events_tenant_id', table_name='guest_credit_events')

    # Drop guest_credit_events table
    op.drop_table('guest_credit_events')

    # Remove audience column from promotions
    op.drop_column('promotions', 'audience')
