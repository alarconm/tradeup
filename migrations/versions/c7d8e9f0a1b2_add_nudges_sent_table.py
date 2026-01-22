"""Add nudges_sent table for tracking sent nudges

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-01-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'b6c7d8e9f0a1'
branch_labels = None
depends_on = None


def upgrade():
    """Create nudges_sent table for tracking sent nudges and preventing duplicates."""
    op.create_table(
        'nudges_sent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('nudge_type', sa.String(50), nullable=False),
        sa.Column('context_data', sa.JSON(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('delivery_method', sa.String(30), nullable=True, default='email'),
        sa.Column('delivery_status', sa.String(30), nullable=True, default='sent'),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_nudges_sent_tenant'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], name='fk_nudges_sent_member'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index('ix_nudges_sent_tenant_id', 'nudges_sent', ['tenant_id'])
    op.create_index('ix_nudges_sent_member_id', 'nudges_sent', ['member_id'])
    op.create_index('ix_nudges_sent_nudge_type', 'nudges_sent', ['nudge_type'])
    op.create_index('ix_nudges_sent_member_type', 'nudges_sent', ['member_id', 'nudge_type'])
    op.create_index('ix_nudges_sent_tenant_type_date', 'nudges_sent', ['tenant_id', 'nudge_type', 'sent_at'])


def downgrade():
    """Remove nudges_sent table."""
    op.drop_index('ix_nudges_sent_tenant_type_date', 'nudges_sent')
    op.drop_index('ix_nudges_sent_member_type', 'nudges_sent')
    op.drop_index('ix_nudges_sent_nudge_type', 'nudges_sent')
    op.drop_index('ix_nudges_sent_member_id', 'nudges_sent')
    op.drop_index('ix_nudges_sent_tenant_id', 'nudges_sent')
    op.drop_table('nudges_sent')
