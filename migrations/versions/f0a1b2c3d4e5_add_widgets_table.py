"""Add widgets table for widget builder configurations

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-01-22 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0a1b2c3d4e5'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    """Create widgets table for widget builder configurations."""
    op.create_table(
        'widgets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('widget_type', sa.String(50), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_widgets_tenant'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'widget_type', name='unique_tenant_widget_type')
    )

    # Create indexes for efficient lookups
    op.create_index('ix_widgets_tenant_id', 'widgets', ['tenant_id'])
    op.create_index('ix_widgets_widget_type', 'widgets', ['widget_type'])


def downgrade():
    """Remove widgets table."""
    op.drop_index('ix_widgets_widget_type', 'widgets')
    op.drop_index('ix_widgets_tenant_id', 'widgets')
    op.drop_table('widgets')
