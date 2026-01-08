"""
CSV Member Import API for TradeUp.

Provides endpoints for bulk importing members from CSV files.
"""
import csv
import io
from flask import Blueprint, request, jsonify
from datetime import datetime
from ..extensions import db
from ..models.member import Member, MembershipTier
from ..models.tenant import Tenant
from ..middleware.shop_auth import require_shop_auth

member_import_bp = Blueprint('member_import', __name__)


@member_import_bp.route('/template', methods=['GET'])
@require_shop_auth
def get_csv_template():
    """
    Get the CSV template for member import.
    Returns column headers and example data.
    """
    return jsonify({
        'columns': [
            {'name': 'email', 'required': True, 'description': 'Member email address'},
            {'name': 'first_name', 'required': True, 'description': 'First name'},
            {'name': 'last_name', 'required': True, 'description': 'Last name'},
            {'name': 'phone', 'required': False, 'description': 'Phone number'},
            {'name': 'tier_name', 'required': False, 'description': 'Tier name (e.g., Bronze, Silver)'},
            {'name': 'shopify_customer_id', 'required': False, 'description': 'Shopify customer ID (if known)'},
            {'name': 'notes', 'required': False, 'description': 'Additional notes'},
        ],
        'example_csv': 'email,first_name,last_name,phone,tier_name\njohn@example.com,John,Doe,555-1234,Bronze\njane@example.com,Jane,Smith,,Silver',
        'instructions': [
            'CSV must include header row',
            'email and first_name are required fields',
            'tier_name should match existing tier names exactly',
            'Phone numbers will be normalized automatically',
            'Duplicate emails will be skipped',
        ]
    })


@member_import_bp.route('/preview', methods=['POST'])
@require_shop_auth
def preview_import():
    """
    Preview a CSV file before importing.
    Validates data and returns preview of what will be imported.
    """
    tenant_id = request.tenant_id

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400

    try:
        # Read and parse CSV
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        # Get existing emails to check for duplicates
        existing_emails = set(
            email[0].lower() for email in
            db.session.query(Member.email).filter(Member.tenant_id == tenant_id).all()
        )

        # Get available tiers
        tiers = {
            tier.name.lower(): tier.id
            for tier in MembershipTier.query.filter_by(
                tenant_id=tenant_id, is_active=True
            ).all()
        }

        # Process rows
        valid_rows = []
        invalid_rows = []
        duplicate_rows = []

        for i, row in enumerate(reader, start=2):  # Start at 2 (after header)
            email = row.get('email', '').strip().lower()
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            phone = row.get('phone', '').strip()
            tier_name = row.get('tier_name', '').strip()
            shopify_customer_id = row.get('shopify_customer_id', '').strip()
            notes = row.get('notes', '').strip()

            errors = []

            # Validate required fields
            if not email:
                errors.append('Missing email')
            elif '@' not in email:
                errors.append('Invalid email format')

            if not first_name:
                errors.append('Missing first_name')

            # Check for duplicates
            if email and email in existing_emails:
                duplicate_rows.append({
                    'row': i,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'reason': 'Member already exists',
                })
                continue

            # Validate tier if provided
            tier_id = None
            if tier_name:
                tier_id = tiers.get(tier_name.lower())
                if not tier_id:
                    errors.append(f'Unknown tier: {tier_name}')

            if errors:
                invalid_rows.append({
                    'row': i,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'errors': errors,
                })
            else:
                valid_rows.append({
                    'row': i,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'tier_name': tier_name,
                    'tier_id': tier_id,
                    'shopify_customer_id': shopify_customer_id,
                    'notes': notes,
                })

        return jsonify({
            'total_rows': len(valid_rows) + len(invalid_rows) + len(duplicate_rows),
            'valid_count': len(valid_rows),
            'invalid_count': len(invalid_rows),
            'duplicate_count': len(duplicate_rows),
            'valid_rows': valid_rows[:10],  # Preview first 10
            'invalid_rows': invalid_rows[:10],
            'duplicate_rows': duplicate_rows[:10],
            'available_tiers': list(tiers.keys()),
        })

    except Exception as e:
        return jsonify({'error': f'Failed to parse CSV: {str(e)}'}), 400


@member_import_bp.route('/import', methods=['POST'])
@require_shop_auth
def import_members():
    """
    Import members from a CSV file.
    """
    tenant_id = request.tenant_id

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    skip_duplicates = request.form.get('skip_duplicates', 'true').lower() == 'true'
    default_tier_id = request.form.get('default_tier_id')

    if default_tier_id:
        default_tier_id = int(default_tier_id)

    try:
        # Read and parse CSV
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        # Get existing emails
        existing_emails = set(
            email[0].lower() for email in
            db.session.query(Member.email).filter(Member.tenant_id == tenant_id).all()
        )

        # Get available tiers
        tiers = {
            tier.name.lower(): tier.id
            for tier in MembershipTier.query.filter_by(
                tenant_id=tenant_id, is_active=True
            ).all()
        }

        # Process and import
        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            email = row.get('email', '').strip().lower()
            first_name = row.get('first_name', '').strip()
            last_name = row.get('last_name', '').strip()
            phone = row.get('phone', '').strip()
            tier_name = row.get('tier_name', '').strip()
            shopify_customer_id = row.get('shopify_customer_id', '').strip()
            notes = row.get('notes', '').strip()

            # Skip if invalid
            if not email or '@' not in email or not first_name:
                errors.append({
                    'row': i,
                    'email': email,
                    'error': 'Missing required fields',
                })
                continue

            # Skip duplicates
            if email in existing_emails:
                if skip_duplicates:
                    skipped += 1
                    continue
                else:
                    errors.append({
                        'row': i,
                        'email': email,
                        'error': 'Duplicate email',
                    })
                    continue

            # Determine tier
            tier_id = None
            if tier_name:
                tier_id = tiers.get(tier_name.lower())
            if not tier_id and default_tier_id:
                tier_id = default_tier_id

            # Generate member number
            member_count = db.session.query(Member).filter(
                Member.tenant_id == tenant_id
            ).count()
            member_number = f"TU{tenant_id:04d}{member_count + imported + 1:06d}"

            try:
                member = Member(
                    tenant_id=tenant_id,
                    email=email,
                    first_name=first_name,
                    last_name=last_name or '',
                    phone=phone,
                    tier_id=tier_id,
                    shopify_customer_id=shopify_customer_id if shopify_customer_id else None,
                    member_number=member_number,
                    status='active',
                    created_at=datetime.utcnow(),
                )
                db.session.add(member)
                existing_emails.add(email)
                imported += 1

            except Exception as e:
                errors.append({
                    'row': i,
                    'email': email,
                    'error': str(e),
                })

        # Commit all at once
        db.session.commit()

        return jsonify({
            'success': True,
            'imported': imported,
            'skipped': skipped,
            'error_count': len(errors),
            'errors': errors[:20],  # Return first 20 errors
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Import failed: {str(e)}'}), 500


@member_import_bp.route('/export', methods=['GET'])
@require_shop_auth
def export_members():
    """
    Export members to CSV.
    """
    tenant_id = request.tenant_id
    tier_filter = request.args.get('tier')
    status_filter = request.args.get('status', 'active')

    try:
        query = db.session.query(Member).filter(Member.tenant_id == tenant_id)

        if status_filter:
            query = query.filter(Member.status == status_filter)

        if tier_filter:
            tier = MembershipTier.query.filter_by(
                tenant_id=tenant_id, name=tier_filter
            ).first()
            if tier:
                query = query.filter(Member.tier_id == tier.id)

        members = query.all()

        # Build CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'member_number',
            'email',
            'first_name',
            'last_name',
            'phone',
            'tier_name',
            'status',
            'total_trade_ins',
            'total_credits_issued',
            'created_at',
            'last_trade_in_at',
        ])

        # Data
        for member in members:
            tier_name = member.tier.name if member.tier else ''
            writer.writerow([
                member.member_number,
                member.email,
                member.first_name,
                member.last_name or '',
                member.phone or '',
                tier_name,
                member.status,
                member.trade_in_count if hasattr(member, 'trade_in_count') else 0,
                float(member.total_credits_issued) if hasattr(member, 'total_credits_issued') else 0,
                member.created_at.isoformat() if member.created_at else '',
                member.last_trade_in_at.isoformat() if hasattr(member, 'last_trade_in_at') and member.last_trade_in_at else '',
            ])

        csv_content = output.getvalue()
        return jsonify({
            'csv_content': csv_content,
            'filename': f'members_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv',
            'total_members': len(members),
        })

    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500
