"""Add support tickets table for post-support review emails

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-01-21

Story: RC-008 - Add post-support review prompt
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y3z4a5b6c7d8'
down_revision = 'x2y3z4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    """Create support_tickets table for tracking post-support review emails."""
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('external_ticket_id', sa.String(100), nullable=False),
        sa.Column('external_source', sa.String(50), nullable=True, default='gorgias'),
        sa.Column('customer_email', sa.String(255), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('member_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='open'),
        sa.Column('satisfaction', sa.String(20), nullable=True, default='not_rated'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('review_email_sent_at', sa.DateTime(), nullable=True),
        sa.Column('review_email_opened_at', sa.DateTime(), nullable=True),
        sa.Column('review_email_clicked_at', sa.DateTime(), nullable=True),
        sa.Column('review_email_tracking_id', sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index('ix_support_tickets_tenant_id', 'support_tickets', ['tenant_id'])
    op.create_index('ix_support_tickets_external_ticket_id', 'support_tickets', ['external_ticket_id'])
    op.create_index('ix_support_tickets_tracking_id', 'support_tickets', ['review_email_tracking_id'], unique=True)
    op.create_index('ix_support_tickets_status', 'support_tickets', ['status'])


def downgrade():
    """Remove support_tickets table."""
    op.drop_index('ix_support_tickets_status', table_name='support_tickets')
    op.drop_index('ix_support_tickets_tracking_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_external_ticket_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_tenant_id', table_name='support_tickets')
    op.drop_table('support_tickets')
