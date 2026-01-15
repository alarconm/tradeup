"""Add birthday fields to members table.

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 't8u9v0w1x2y3'
down_revision = 's7t8u9v0w1x2'
branch_labels = None
depends_on = None


def upgrade():
    """Add birthday tracking columns to members table."""
    # Birthday date (just month and day, stored as date with year 2000)
    op.add_column('members', sa.Column('birthday', sa.Date(), nullable=True))

    # Track when last birthday reward was given (to avoid duplicates)
    op.add_column('members', sa.Column('last_birthday_reward_year', sa.Integer(), nullable=True))

    # Create index for birthday queries (month-day lookups)
    op.create_index('ix_members_birthday', 'members', ['birthday'])


def downgrade():
    """Remove birthday columns."""
    op.drop_index('ix_members_birthday', table_name='members')
    op.drop_column('members', 'last_birthday_reward_year')
    op.drop_column('members', 'birthday')
