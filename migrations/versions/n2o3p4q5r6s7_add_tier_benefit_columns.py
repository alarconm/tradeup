"""Add tier benefit columns to membership_tiers.

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-01-07

Adds new columns for comprehensive tier benefits:
- yearly_price: Optional yearly subscription pricing
- purchase_cashback_pct: Percentage cashback on purchases
- monthly_credit_amount: Monthly store credit reward
- credit_expiration_days: Days until credit expires (null = never)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n2o3p4q5r6s7'
down_revision = 'm1n2o3p4q5r6'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to membership_tiers
    with op.batch_alter_table('membership_tiers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yearly_price', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('purchase_cashback_pct', sa.Numeric(5, 2), nullable=True, default=0))
        batch_op.add_column(sa.Column('monthly_credit_amount', sa.Numeric(10, 2), nullable=True, default=0))
        batch_op.add_column(sa.Column('credit_expiration_days', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('membership_tiers', schema=None) as batch_op:
        batch_op.drop_column('credit_expiration_days')
        batch_op.drop_column('monthly_credit_amount')
        batch_op.drop_column('purchase_cashback_pct')
        batch_op.drop_column('yearly_price')
