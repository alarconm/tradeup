"""Replace Stripe with Shopify subscription fields

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-01-05 11:00:00.000000

This migration:
1. Removes Stripe-specific columns from members and membership_tiers
2. Adds Shopify subscription tracking columns to members
3. Adds Shopify selling plan ID to membership_tiers

NOTE: Made idempotent - checks if columns exist before adding/dropping.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
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

    # Add new Shopify subscription columns to members (if they don't exist)
    if not column_exists(conn, 'members', 'shopify_subscription_contract_id'):
        op.add_column('members', sa.Column('shopify_subscription_contract_id', sa.String(length=100), nullable=True))

    if not column_exists(conn, 'members', 'subscription_status'):
        op.add_column('members', sa.Column('subscription_status', sa.String(length=20), server_default='none', nullable=True))

    if not column_exists(conn, 'members', 'tier_assigned_by'):
        op.add_column('members', sa.Column('tier_assigned_by', sa.String(length=100), nullable=True))

    if not column_exists(conn, 'members', 'tier_assigned_at'):
        op.add_column('members', sa.Column('tier_assigned_at', sa.DateTime(), nullable=True))

    if not column_exists(conn, 'members', 'tier_expires_at'):
        op.add_column('members', sa.Column('tier_expires_at', sa.DateTime(), nullable=True))

    # Remove Stripe columns from members (if they exist)
    if column_exists(conn, 'members', 'stripe_customer_id'):
        op.drop_column('members', 'stripe_customer_id')

    if column_exists(conn, 'members', 'stripe_subscription_id'):
        op.drop_column('members', 'stripe_subscription_id')

    if column_exists(conn, 'members', 'payment_status'):
        op.drop_column('members', 'payment_status')

    if column_exists(conn, 'members', 'current_period_start'):
        op.drop_column('members', 'current_period_start')

    if column_exists(conn, 'members', 'current_period_end'):
        op.drop_column('members', 'current_period_end')

    if column_exists(conn, 'members', 'cancel_at_period_end'):
        op.drop_column('members', 'cancel_at_period_end')

    # Update membership_tiers: add Shopify column (if doesn't exist)
    if not column_exists(conn, 'membership_tiers', 'shopify_selling_plan_id'):
        op.add_column('membership_tiers', sa.Column('shopify_selling_plan_id', sa.String(length=100), nullable=True))

    # Remove Stripe columns from membership_tiers (if they exist)
    if column_exists(conn, 'membership_tiers', 'stripe_product_id'):
        op.drop_column('membership_tiers', 'stripe_product_id')

    if column_exists(conn, 'membership_tiers', 'stripe_price_id'):
        op.drop_column('membership_tiers', 'stripe_price_id')


def downgrade():
    # Restore Stripe columns to membership_tiers
    with op.batch_alter_table('membership_tiers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_product_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('stripe_price_id', sa.String(length=50), nullable=True))
        batch_op.drop_column('shopify_selling_plan_id')

    # Restore Stripe columns to members
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_customer_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('stripe_subscription_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('payment_status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('current_period_start', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('current_period_end', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('cancel_at_period_end', sa.Boolean(), nullable=True))

        # Remove Shopify columns
        batch_op.drop_column('tier_expires_at')
        batch_op.drop_column('tier_assigned_at')
        batch_op.drop_column('tier_assigned_by')
        batch_op.drop_column('subscription_status')
        batch_op.drop_column('shopify_subscription_contract_id')
