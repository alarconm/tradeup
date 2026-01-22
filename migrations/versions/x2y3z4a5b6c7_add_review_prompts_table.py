"""Add review prompts table for in-app review collection.

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x2y3z4a5b6c7'
down_revision = 'w1x2y3z4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    """Create review_prompts table for tracking review prompt interactions."""
    op.create_table(
        'review_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('prompt_shown_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('response', sa.String(20), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_review_prompts_tenant_id', 'review_prompts', ['tenant_id'])
    op.create_index('ix_review_prompts_prompt_shown_at', 'review_prompts', ['prompt_shown_at'])


def downgrade():
    """Drop review_prompts table."""
    op.drop_index('ix_review_prompts_prompt_shown_at', table_name='review_prompts')
    op.drop_index('ix_review_prompts_tenant_id', table_name='review_prompts')
    op.drop_table('review_prompts')
