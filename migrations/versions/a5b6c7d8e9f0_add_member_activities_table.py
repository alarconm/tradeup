"""Add member_activities table for activity tracking

Revision ID: a5b6c7d8e9f0
Revises: z4a5b6c7d8e9
Create Date: 2026-01-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5b6c7d8e9f0'
down_revision = 'z4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade():
    """Create member_activities table for tracking member events."""
    op.create_table(
        'member_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('activity_date', sa.DateTime(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('anniversary_year', sa.Integer(), nullable=True),
        sa.Column('reward_type', sa.String(30), nullable=True),
        sa.Column('reward_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('reward_reference', sa.String(100), nullable=True),
        sa.Column('related_badge_id', sa.Integer(), nullable=True),
        sa.Column('related_milestone_id', sa.Integer(), nullable=True),
        sa.Column('related_tier_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ),
        sa.ForeignKeyConstraint(['related_badge_id'], ['badges.id'], ),
        sa.ForeignKeyConstraint(['related_milestone_id'], ['milestones.id'], ),
        sa.ForeignKeyConstraint(['related_tier_id'], ['membership_tiers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_member_activities_tenant_id', 'member_activities', ['tenant_id'])
    op.create_index('ix_member_activities_member_id', 'member_activities', ['member_id'])
    op.create_index('ix_member_activities_activity_type', 'member_activities', ['activity_type'])
    op.create_index('ix_member_activities_activity_date', 'member_activities', ['activity_date'])
    op.create_index('ix_member_activity_type', 'member_activities', ['member_id', 'activity_type'])
    op.create_index('ix_member_activity_date', 'member_activities', ['member_id', 'activity_date'])
    op.create_index('ix_tenant_activity_type', 'member_activities', ['tenant_id', 'activity_type'])


def downgrade():
    """Drop member_activities table."""
    op.drop_index('ix_tenant_activity_type', table_name='member_activities')
    op.drop_index('ix_member_activity_date', table_name='member_activities')
    op.drop_index('ix_member_activity_type', table_name='member_activities')
    op.drop_index('ix_member_activities_activity_date', table_name='member_activities')
    op.drop_index('ix_member_activities_activity_type', table_name='member_activities')
    op.drop_index('ix_member_activities_member_id', table_name='member_activities')
    op.drop_index('ix_member_activities_tenant_id', table_name='member_activities')
    op.drop_table('member_activities')
