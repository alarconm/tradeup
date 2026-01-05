"""Add partner integration tables

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-01-05 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    # Create partner_integrations table
    op.create_table('partner_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('partner_type', sa.String(length=50), nullable=True, server_default='wordpress'),
        sa.Column('api_url', sa.String(length=500), nullable=True),
        sa.Column('api_token', sa.String(length=500), nullable=True),
        sa.Column('webhook_secret', sa.String(length=100), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('sync_trade_ins', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('sync_bonuses', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('sync_members', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('field_mapping', sa.JSON(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_status', sa.String(length=20), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('sync_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_tenant_partner_slug')
    )

    # Create partner_sync_logs table
    op.create_table('partner_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=True),
        sa.Column('record_reference', sa.String(length=100), nullable=True),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['integration_id'], ['partner_integrations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('partner_sync_logs')
    op.drop_table('partner_integrations')
