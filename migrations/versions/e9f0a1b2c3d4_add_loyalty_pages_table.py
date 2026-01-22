"""Add loyalty_pages table for page builder configurations

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-01-22 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f0a1b2c3d4'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade():
    """Create loyalty_pages table for page builder configurations."""
    op.create_table(
        'loyalty_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('page_config', sa.JSON(), nullable=False),
        sa.Column('draft_config', sa.JSON(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, default=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_loyalty_pages_tenant'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', name='unique_tenant_loyalty_page')
    )

    # Create index for efficient tenant lookups
    op.create_index('ix_loyalty_pages_tenant_id', 'loyalty_pages', ['tenant_id'])


def downgrade():
    """Remove loyalty_pages table."""
    op.drop_index('ix_loyalty_pages_tenant_id', 'loyalty_pages')
    op.drop_table('loyalty_pages')
