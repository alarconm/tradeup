"""Add anniversary reward tracking field to members table.

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2026-01-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z4a5b6c7d8e9'
down_revision = 'y3z4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade():
    """Add anniversary reward tracking column to members table."""
    # Track when last anniversary reward was given (to avoid duplicates)
    op.add_column('members', sa.Column('last_anniversary_reward_year', sa.Integer(), nullable=True))


def downgrade():
    """Remove anniversary reward column."""
    op.drop_column('members', 'last_anniversary_reward_year')
