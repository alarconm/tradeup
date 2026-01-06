"""
Partner Integration model.
Stores configuration for external partner systems (ORB, etc.)
"""
from datetime import datetime
from ..extensions import db


class PartnerIntegration(db.Model):
    """
    Configuration for external partner integrations.

    Partners can receive trade-in data, bonus notifications, etc.
    Example: ORB Sports Cards WordPress site receiving trade-in entries
    for their cash ledger system.
    """
    __tablename__ = 'partner_integrations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)

    # Partner identification
    name = db.Column(db.String(100), nullable=False)  # "ORB Sports Cards"
    slug = db.Column(db.String(50), nullable=False)   # "orb-sports-cards"
    partner_type = db.Column(db.String(50), default='wordpress')  # wordpress, shopify, custom

    # API Configuration
    api_url = db.Column(db.String(500))  # "https://orbsportscards.com/wp-json/mykd/v1"
    api_token = db.Column(db.String(500))  # Encrypted API token
    webhook_secret = db.Column(db.String(100))  # For incoming webhooks

    # Sync settings
    enabled = db.Column(db.Boolean, default=True)
    sync_trade_ins = db.Column(db.Boolean, default=True)  # Push trade-ins to partner
    sync_bonuses = db.Column(db.Boolean, default=True)    # Push bonus issuance to partner
    sync_members = db.Column(db.Boolean, default=False)   # Push member enrollments

    # Field mapping (JSON) - maps TradeUp fields to partner fields
    field_mapping = db.Column(db.JSON, default=dict)
    # Example: {"category": "kind", "total_trade_value": "amount"}

    # Metadata
    last_sync_at = db.Column(db.DateTime)
    last_sync_status = db.Column(db.String(20))  # success, failed, pending
    last_sync_error = db.Column(db.Text)
    sync_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sync_logs = db.relationship('PartnerSyncLog', backref='integration', lazy='dynamic', cascade='all, delete-orphan')

    # Unique constraint per tenant
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'slug', name='uq_tenant_partner_slug'),
    )

    def __repr__(self):
        return f'<PartnerIntegration {self.name}>'

    def to_dict(self, include_secrets=False):
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'name': self.name,
            'slug': self.slug,
            'partner_type': self.partner_type,
            'api_url': self.api_url,
            'enabled': self.enabled,
            'sync_trade_ins': self.sync_trade_ins,
            'sync_bonuses': self.sync_bonuses,
            'sync_members': self.sync_members,
            'field_mapping': self.field_mapping,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'last_sync_status': self.last_sync_status,
            'sync_count': self.sync_count,
            'created_at': self.created_at.isoformat()
        }

        if include_secrets:
            data['api_token'] = self.api_token
            data['webhook_secret'] = self.webhook_secret

        return data


class PartnerSyncLog(db.Model):
    """
    Log of sync operations with partners.
    Tracks what was sent and the response.
    """
    __tablename__ = 'partner_sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    integration_id = db.Column(db.Integer, db.ForeignKey('partner_integrations.id'), nullable=False)

    # What was synced
    sync_type = db.Column(db.String(50), nullable=False)  # trade_in, bonus, member
    record_id = db.Column(db.Integer)  # TradeInBatch.id, Member.id, etc.
    record_reference = db.Column(db.String(100))  # TI-20260105-001, etc.

    # Request/Response
    request_payload = db.Column(db.JSON)
    response_status = db.Column(db.Integer)  # HTTP status code
    response_body = db.Column(db.JSON)

    # Status
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PartnerSyncLog {self.sync_type} {self.record_reference}>'

    def to_dict(self):
        return {
            'id': self.id,
            'integration_id': self.integration_id,
            'sync_type': self.sync_type,
            'record_id': self.record_id,
            'record_reference': self.record_reference,
            'response_status': self.response_status,
            'status': self.status,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat()
        }
