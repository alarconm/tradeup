"""Add shopify_customer_gid and partner_customer_id to members

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
Create Date: 2026-01-05 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5c6d7e8f9a0'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    # Add new Shopify-native columns to members table
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shopify_customer_gid', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('partner_customer_id', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.drop_column('partner_customer_id')
        batch_op.drop_column('shopify_customer_gid')
