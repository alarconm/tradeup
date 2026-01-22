"""Add nudge effectiveness tracking columns

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-01-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    """Add conversion tracking and effectiveness columns to nudges_sent table."""
    # Add conversion tracking columns
    op.add_column('nudges_sent', sa.Column('converted_at', sa.DateTime(), nullable=True))
    op.add_column('nudges_sent', sa.Column('order_id', sa.String(100), nullable=True))
    op.add_column('nudges_sent', sa.Column('order_total', sa.Numeric(10, 2), nullable=True))
    op.add_column('nudges_sent', sa.Column('tracking_id', sa.String(100), nullable=True))

    # Create index on tracking_id for fast lookups
    op.create_index('ix_nudges_sent_tracking_id', 'nudges_sent', ['tracking_id'], unique=True)


def downgrade():
    """Remove conversion tracking columns from nudges_sent table."""
    op.drop_index('ix_nudges_sent_tracking_id', 'nudges_sent')
    op.drop_column('nudges_sent', 'tracking_id')
    op.drop_column('nudges_sent', 'order_total')
    op.drop_column('nudges_sent', 'order_id')
    op.drop_column('nudges_sent', 'converted_at')
