"""Add nudge_configs table for configurable nudge settings per tenant.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6c7d8e9f0a1'
down_revision = 'a5b6c7d8e9f0'
branch_labels = None
depends_on = None


def upgrade():
    """Create nudge_configs table for storing nudge configurations per tenant."""
    op.create_table(
        'nudge_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('nudge_type', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('frequency_days', sa.Integer(), nullable=False, server_default=sa.text('7')),
        sa.Column('message_template', sa.Text(), nullable=False),
        sa.Column('config_options', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'nudge_type', name='unique_tenant_nudge_type'),
    )

    # Create indexes for common queries
    op.create_index('ix_nudge_configs_tenant_id', 'nudge_configs', ['tenant_id'])
    op.create_index('ix_nudge_configs_nudge_type', 'nudge_configs', ['nudge_type'])
    op.create_index('ix_nudge_configs_enabled', 'nudge_configs', ['tenant_id', 'is_enabled'])


def downgrade():
    """Drop nudge_configs table."""
    op.drop_index('ix_nudge_configs_enabled', table_name='nudge_configs')
    op.drop_index('ix_nudge_configs_nudge_type', table_name='nudge_configs')
    op.drop_index('ix_nudge_configs_tenant_id', table_name='nudge_configs')
    op.drop_table('nudge_configs')
