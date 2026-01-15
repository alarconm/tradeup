"""Add guest_points table for guest checkout points.

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'u9v0w1x2y3z4'
down_revision = 't8u9v0w1x2y3'
branch_labels = None
depends_on = None


def upgrade():
    """Create guest_points table."""
    op.create_table(
        'guest_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('shopify_customer_id', sa.String(50), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(100), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('order_number', sa.String(50), nullable=True),
        sa.Column('order_total', sa.Numeric(10, 2), nullable=True),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('claimed_by_member_id', sa.Integer(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['claimed_by_member_id'], ['members.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_guest_points_tenant_email', 'guest_points', ['tenant_id', 'email'])
    op.create_index('ix_guest_points_tenant_status', 'guest_points', ['tenant_id', 'status'])


def downgrade():
    """Drop guest_points table."""
    op.drop_index('ix_guest_points_tenant_status', table_name='guest_points')
    op.drop_index('ix_guest_points_tenant_email', table_name='guest_points')
    op.drop_table('guest_points')
