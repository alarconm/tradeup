"""
Trade-In Ledger API - Simplified trade-in tracking endpoints.

Simple CRUD operations for recording trade-in transactions.
No complex workflows or item-level tracking.
"""
from flask import Blueprint, request, jsonify, g
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, desc
from ..extensions import db
from ..models import TradeInLedger, Member
from ..middleware.shopify_auth import require_shopify_auth

trade_ledger_bp = Blueprint('trade_ledger', __name__)


@trade_ledger_bp.route('/', methods=['GET'])
@require_shopify_auth
def list_entries():
    """
    List all trade-in ledger entries for the tenant.

    Query params:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    - member_id: Filter by member ID
    - category: Filter by category
    - start_date: Filter from date (ISO format)
    - end_date: Filter to date (ISO format)
    - search: Search by reference, customer name, or notes
    """
    try:
        tenant_id = g.tenant_id

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        member_id = request.args.get('member_id', type=int)
        category = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        search = request.args.get('search')

        query = TradeInLedger.query.filter_by(tenant_id=tenant_id)

        # Apply filters
        if member_id:
            query = query.filter(TradeInLedger.member_id == member_id)

        if category:
            query = query.filter(TradeInLedger.category == category)

        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(TradeInLedger.trade_date >= start)
            except ValueError:
                pass

        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(TradeInLedger.trade_date <= end)
            except ValueError:
                pass

        if search:
            search_term = f'%{search}%'
            query = query.filter(
                db.or_(
                    TradeInLedger.reference.ilike(search_term),
                    TradeInLedger.guest_name.ilike(search_term),
                    TradeInLedger.notes.ilike(search_term),
                    TradeInLedger.category.ilike(search_term),
                )
            )

        # Order by most recent first
        query = query.order_by(desc(TradeInLedger.trade_date))

        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'entries': [entry.to_dict() for entry in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
        })
    except Exception as e:
        import traceback
        print(f"[TradeLedger] Error listing entries: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/', methods=['POST'])
@require_shopify_auth
def create_entry():
    """
    Create a new trade-in ledger entry.

    Request body:
    - member_id: Optional member ID
    - guest_name, guest_email, guest_phone: Optional guest info
    - total_value: Total trade-in value (required)
    - cash_amount: Amount paid in cash (default: 0)
    - credit_amount: Amount paid as store credit (default: 0)
    - category: Optional category name
    - collection_id: Optional Shopify collection ID
    - collection_name: Optional collection name
    - notes: Optional notes
    - created_by: Employee who processed
    - trade_date: Optional trade date (defaults to now)
    """
    try:
        tenant_id = g.tenant_id
        data = request.get_json() or {}

        # Validate required field
        total_value = data.get('total_value')
        if total_value is None:
            return jsonify({'error': 'total_value is required'}), 400

        try:
            total_value = Decimal(str(total_value))
        except (InvalidOperation, ValueError):
            return jsonify({'error': 'Invalid total_value'}), 400

        if total_value < 0:
            return jsonify({'error': 'total_value cannot be negative'}), 400

        # Parse amounts
        try:
            cash_amount = Decimal(str(data.get('cash_amount', 0)))
            credit_amount = Decimal(str(data.get('credit_amount', 0)))
        except (InvalidOperation, ValueError):
            return jsonify({'error': 'Invalid cash_amount or credit_amount'}), 400

        # Validate member if provided
        member_id = data.get('member_id')
        if member_id:
            member = Member.query.filter_by(
                id=member_id,
                tenant_id=tenant_id
            ).first()
            if not member:
                return jsonify({'error': 'Member not found'}), 404

        # Parse trade date if provided
        trade_date = datetime.utcnow()
        if data.get('trade_date'):
            try:
                trade_date = datetime.fromisoformat(
                    data['trade_date'].replace('Z', '+00:00')
                )
            except ValueError:
                return jsonify({'error': 'Invalid trade_date format'}), 400

        # Generate reference
        reference = TradeInLedger.generate_reference(tenant_id)

        # Create entry
        entry = TradeInLedger(
            tenant_id=tenant_id,
            member_id=member_id,
            guest_name=data.get('guest_name'),
            guest_email=data.get('guest_email'),
            guest_phone=data.get('guest_phone'),
            reference=reference,
            trade_date=trade_date,
            total_value=total_value,
            cash_amount=cash_amount,
            credit_amount=credit_amount,
            category=data.get('category'),
            collection_id=data.get('collection_id'),
            collection_name=data.get('collection_name'),
            notes=data.get('notes'),
            created_by=data.get('created_by'),
        )

        db.session.add(entry)
        db.session.commit()

        return jsonify(entry.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"[TradeLedger] Error creating entry: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/<int:entry_id>', methods=['GET'])
@require_shopify_auth
def get_entry(entry_id: int):
    """Get a single trade-in ledger entry."""
    try:
        tenant_id = g.tenant_id

        entry = TradeInLedger.query.filter_by(
            id=entry_id,
            tenant_id=tenant_id
        ).first()

        if not entry:
            return jsonify({'error': 'Entry not found'}), 404

        return jsonify(entry.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/<int:entry_id>', methods=['PUT'])
@require_shopify_auth
def update_entry(entry_id: int):
    """
    Update a trade-in ledger entry.

    Can update: total_value, cash_amount, credit_amount, category,
    collection_id, collection_name, notes, trade_date
    """
    try:
        tenant_id = g.tenant_id
        data = request.get_json() or {}

        entry = TradeInLedger.query.filter_by(
            id=entry_id,
            tenant_id=tenant_id
        ).first()

        if not entry:
            return jsonify({'error': 'Entry not found'}), 404

        # Update allowed fields
        if 'total_value' in data:
            try:
                entry.total_value = Decimal(str(data['total_value']))
            except (InvalidOperation, ValueError):
                return jsonify({'error': 'Invalid total_value'}), 400

        if 'cash_amount' in data:
            try:
                entry.cash_amount = Decimal(str(data['cash_amount']))
            except (InvalidOperation, ValueError):
                return jsonify({'error': 'Invalid cash_amount'}), 400

        if 'credit_amount' in data:
            try:
                entry.credit_amount = Decimal(str(data['credit_amount']))
            except (InvalidOperation, ValueError):
                return jsonify({'error': 'Invalid credit_amount'}), 400

        if 'category' in data:
            entry.category = data['category']

        if 'collection_id' in data:
            entry.collection_id = data['collection_id']

        if 'collection_name' in data:
            entry.collection_name = data['collection_name']

        if 'notes' in data:
            entry.notes = data['notes']

        if 'trade_date' in data and data['trade_date']:
            try:
                entry.trade_date = datetime.fromisoformat(
                    data['trade_date'].replace('Z', '+00:00')
                )
            except ValueError:
                return jsonify({'error': 'Invalid trade_date format'}), 400

        # Update guest info if provided
        if 'guest_name' in data:
            entry.guest_name = data['guest_name']
        if 'guest_email' in data:
            entry.guest_email = data['guest_email']
        if 'guest_phone' in data:
            entry.guest_phone = data['guest_phone']

        db.session.commit()

        return jsonify(entry.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/<int:entry_id>', methods=['DELETE'])
@require_shopify_auth
def delete_entry(entry_id: int):
    """Delete a trade-in ledger entry."""
    try:
        tenant_id = g.tenant_id

        entry = TradeInLedger.query.filter_by(
            id=entry_id,
            tenant_id=tenant_id
        ).first()

        if not entry:
            return jsonify({'error': 'Entry not found'}), 404

        db.session.delete(entry)
        db.session.commit()

        return jsonify({'success': True, 'deleted_id': entry_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/by-member/<int:member_id>', methods=['GET'])
@require_shopify_auth
def get_member_entries(member_id: int):
    """Get all trade-in entries for a specific member."""
    try:
        tenant_id = g.tenant_id

        # Verify member belongs to tenant
        member = Member.query.filter_by(
            id=member_id,
            tenant_id=tenant_id
        ).first()

        if not member:
            return jsonify({'error': 'Member not found'}), 404

        entries = (
            TradeInLedger.query
            .filter_by(tenant_id=tenant_id, member_id=member_id)
            .order_by(desc(TradeInLedger.trade_date))
            .all()
        )

        return jsonify({
            'member_id': member_id,
            'member_name': member.name,
            'entries': [entry.to_dict() for entry in entries],
            'total_entries': len(entries),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/summary', methods=['GET'])
@require_shopify_auth
def get_summary():
    """
    Get summary statistics for the trade-in ledger.

    Query params:
    - start_date: Filter from date (ISO format)
    - end_date: Filter to date (ISO format)
    """
    try:
        tenant_id = g.tenant_id

        query = db.session.query(
            func.count(TradeInLedger.id).label('total_entries'),
            func.coalesce(func.sum(TradeInLedger.total_value), 0).label('total_value'),
            func.coalesce(func.sum(TradeInLedger.cash_amount), 0).label('total_cash'),
            func.coalesce(func.sum(TradeInLedger.credit_amount), 0).label('total_credit'),
        ).filter(TradeInLedger.tenant_id == tenant_id)

        # Apply date filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(TradeInLedger.trade_date >= start)
            except ValueError:
                pass

        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(TradeInLedger.trade_date <= end)
            except ValueError:
                pass

        result = query.first()

        # Get category breakdown
        category_query = (
            db.session.query(
                TradeInLedger.category,
                func.count(TradeInLedger.id).label('count'),
                func.coalesce(func.sum(TradeInLedger.total_value), 0).label('value'),
            )
            .filter(
                TradeInLedger.tenant_id == tenant_id,
                TradeInLedger.category.isnot(None),
            )
            .group_by(TradeInLedger.category)
            .order_by(desc('value'))
            .all()
        )

        categories = [
            {
                'category': row.category,
                'count': row.count,
                'value': float(row.value),
            }
            for row in category_query
        ]

        return jsonify({
            'total_entries': result.total_entries or 0,
            'total_value': float(result.total_value or 0),
            'total_cash': float(result.total_cash or 0),
            'total_credit': float(result.total_credit or 0),
            'categories': categories,
        })
    except Exception as e:
        import traceback
        print(f"[TradeLedger] Error getting summary: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@trade_ledger_bp.route('/categories', methods=['GET'])
@require_shopify_auth
def get_categories():
    """
    Get list of categories used in the ledger.

    Returns distinct categories that have been used.
    """
    try:
        tenant_id = g.tenant_id

        categories = (
            db.session.query(TradeInLedger.category)
            .filter(
                TradeInLedger.tenant_id == tenant_id,
                TradeInLedger.category.isnot(None),
                TradeInLedger.category != '',
            )
            .distinct()
            .order_by(TradeInLedger.category)
            .all()
        )

        return jsonify({
            'categories': [cat[0] for cat in categories if cat[0]]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
