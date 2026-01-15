"""Add gamification tables (badges, streaks, milestones).

Revision ID: s7t8u9v0w1x2
Revises: r6s7t8u9v0w1
Create Date: 2026-01-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's7t8u9v0w1x2'
down_revision = 'r6s7t8u9v0w1'
branch_labels = None
depends_on = None


def upgrade():
    """Create gamification tables for badges, streaks, and milestones."""
    # Badges table
    op.create_table(
        'badges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('icon', sa.String(50), server_default='trophy'),
        sa.Column('color', sa.String(20), server_default='#e85d27'),
        sa.Column('criteria_type', sa.String(50), nullable=False),
        sa.Column('criteria_value', sa.Integer(), server_default='1'),
        sa.Column('points_reward', sa.Integer(), server_default='0'),
        sa.Column('credit_reward', sa.Numeric(10, 2), server_default='0'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_secret', sa.Boolean(), server_default='false'),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_badges_tenant_id', 'badges', ['tenant_id'])
    op.create_index('ix_badges_criteria_type', 'badges', ['criteria_type'])

    # Member Badges table (badges earned by members)
    op.create_table(
        'member_badges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('badge_id', sa.Integer(), nullable=False),
        sa.Column('earned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('progress_max', sa.Integer(), server_default='0'),
        sa.Column('notified', sa.Boolean(), server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['badge_id'], ['badges.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('member_id', 'badge_id', name='unique_member_badge'),
    )
    op.create_index('ix_member_badges_member_id', 'member_badges', ['member_id'])
    op.create_index('ix_member_badges_badge_id', 'member_badges', ['badge_id'])

    # Member Streaks table
    op.create_table(
        'member_streaks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('current_streak', sa.Integer(), server_default='0'),
        sa.Column('longest_streak', sa.Integer(), server_default='0'),
        sa.Column('last_activity_date', sa.Date(), nullable=True),
        sa.Column('streak_type', sa.String(50), server_default='daily'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_member_streaks_member_id', 'member_streaks', ['member_id'])

    # Milestones table
    op.create_table(
        'milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('milestone_type', sa.String(50), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('points_reward', sa.Integer(), server_default='0'),
        sa.Column('credit_reward', sa.Numeric(10, 2), server_default='0'),
        sa.Column('badge_id', sa.Integer(), nullable=True),
        sa.Column('celebration_message', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['badge_id'], ['badges.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_milestones_tenant_id', 'milestones', ['tenant_id'])
    op.create_index('ix_milestones_type', 'milestones', ['milestone_type'])

    # Member Milestones table (milestones achieved by members)
    op.create_table(
        'member_milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('milestone_id', sa.Integer(), nullable=False),
        sa.Column('achieved_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('notified', sa.Boolean(), server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['milestone_id'], ['milestones.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('member_id', 'milestone_id', name='unique_member_milestone'),
    )
    op.create_index('ix_member_milestones_member_id', 'member_milestones', ['member_id'])
    op.create_index('ix_member_milestones_milestone_id', 'member_milestones', ['milestone_id'])


def downgrade():
    """Drop gamification tables."""
    op.drop_table('member_milestones')
    op.drop_table('milestones')
    op.drop_table('member_streaks')
    op.drop_table('member_badges')
    op.drop_table('badges')
