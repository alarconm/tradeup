"""Add icon column to tier_configurations

Revision ID: g1h2i3j4k5l6
Revises: f0a1b2c3d4e5
Create Date: 2026-01-05

"""
from alembic import op
import sqlalchemy as sa


revision = 'g1h2i3j4k5l6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    # Add icon column if it doesn't exist
    conn = op.get_bind()

    # Check if column exists
    result = conn.execute(sa.text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tier_configurations' AND column_name = 'icon'
    """))

    if result.fetchone() is None:
        op.add_column('tier_configurations',
            sa.Column('icon', sa.String(length=50), nullable=True, server_default='star')
        )


def downgrade():
    op.drop_column('tier_configurations', 'icon')
