"""
Authentication API endpoints.
Handles member signup, login, JWT tokens, and password reset.
"""
import os
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
import jwt

from ..extensions import db
from ..models import Member, MembershipTier, Tenant

auth_bp = Blueprint('auth', __name__)

# JWT configuration
JWT_SECRET = os.getenv('JWT_SECRET_KEY', 'dev-secret-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_ACCESS_EXPIRY = timedelta(hours=1)
JWT_REFRESH_EXPIRY = timedelta(days=30)


def create_access_token(member_id: int, tenant_id: int) -> str:
    """Create a short-lived access token."""
    payload = {
        'member_id': member_id,
        'tenant_id': tenant_id,
        'type': 'access',
        'exp': datetime.utcnow() + JWT_ACCESS_EXPIRY,
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(member_id: int, tenant_id: int) -> str:
    """Create a long-lived refresh token."""
    payload = {
        'member_id': member_id,
        'tenant_id': tenant_id,
        'type': 'refresh',
        'exp': datetime.utcnow() + JWT_REFRESH_EXPIRY,
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired')
    except jwt.InvalidTokenError:
        raise ValueError('Invalid token')


def get_current_member():
    """Get current member from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]
    try:
        payload = decode_token(token)
        if payload.get('type') != 'access':
            return None
        return Member.query.get(payload['member_id'])
    except ValueError:
        return None


@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Create a new member account.

    Request body:
        email: string (required)
        password: string (required)
        name: string (optional)
        phone: string (optional)
        tier_id: int (optional) - will be set after payment

    Returns:
        Member data and auth tokens
    """
    data = request.json
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    # Validate required fields
    if not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400
    if not data.get('password'):
        return jsonify({'error': 'Password is required'}), 400
    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Check if email already exists for this tenant
    existing = Member.query.filter_by(
        tenant_id=tenant_id,
        email=data['email'].lower()
    ).first()

    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    # Create member
    member = Member(
        tenant_id=tenant_id,
        email=data['email'].lower(),
        name=data.get('name'),
        phone=data.get('phone'),
        member_number=Member.generate_member_number(tenant_id),
        status='pending',  # Will become 'active' after payment
        email_verification_token=secrets.token_urlsafe(32)
    )
    member.set_password(data['password'])

    db.session.add(member)
    db.session.commit()

    # Generate tokens
    access_token = create_access_token(member.id, tenant_id)
    refresh_token = create_refresh_token(member.id, tenant_id)

    return jsonify({
        'member': member.to_dict(include_subscription=True),
        'access_token': access_token,
        'refresh_token': refresh_token,
        'message': 'Account created. Complete payment to activate membership.'
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login with email and password.

    Request body:
        email: string (required)
        password: string (required)

    Returns:
        Member data and auth tokens
    """
    data = request.json
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        email=data['email'].lower()
    ).first()

    if not member or not member.check_password(data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401

    # Generate tokens
    access_token = create_access_token(member.id, tenant_id)
    refresh_token = create_refresh_token(member.id, tenant_id)

    return jsonify({
        'member': member.to_dict(include_stats=True, include_subscription=True),
        'access_token': access_token,
        'refresh_token': refresh_token
    })


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    Refresh access token using refresh token.

    Request body:
        refresh_token: string (required)

    Returns:
        New access token
    """
    data = request.json
    if not data.get('refresh_token'):
        return jsonify({'error': 'Refresh token is required'}), 400

    try:
        payload = decode_token(data['refresh_token'])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid token type'}), 401

        # Verify member still exists and is valid
        member = Member.query.get(payload['member_id'])
        if not member:
            return jsonify({'error': 'Member not found'}), 401

        # Create new access token
        access_token = create_access_token(member.id, payload['tenant_id'])

        return jsonify({
            'access_token': access_token
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 401


@auth_bp.route('/me', methods=['GET'])
def get_me():
    """
    Get current authenticated member.

    Returns:
        Member data with stats and subscription info
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({
        'member': member.to_dict(include_stats=True, include_subscription=True)
    })


@auth_bp.route('/me', methods=['PUT'])
def update_me():
    """
    Update current member profile.

    Request body:
        name: string (optional)
        phone: string (optional)

    Returns:
        Updated member data
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json

    if 'name' in data:
        member.name = data['name']
    if 'phone' in data:
        member.phone = data['phone']

    db.session.commit()

    return jsonify({
        'member': member.to_dict(include_stats=True, include_subscription=True)
    })


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """
    Change password for authenticated member.

    Request body:
        current_password: string (required)
        new_password: string (required)

    Returns:
        Success message
    """
    member = get_current_member()
    if not member:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json

    if not data.get('current_password') or not data.get('new_password'):
        return jsonify({'error': 'Current and new password are required'}), 400

    if not member.check_password(data['current_password']):
        return jsonify({'error': 'Current password is incorrect'}), 401

    if len(data['new_password']) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    member.set_password(data['new_password'])
    db.session.commit()

    return jsonify({'message': 'Password changed successfully'})


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """
    Request password reset email.

    Request body:
        email: string (required)

    Returns:
        Success message (always returns success for security)
    """
    data = request.json
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    if not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        email=data['email'].lower()
    ).first()

    if member:
        # Generate reset token
        member.email_verification_token = secrets.token_urlsafe(32)
        db.session.commit()

        # TODO: Send password reset email
        # send_password_reset_email(member.email, member.email_verification_token)

    # Always return success to prevent email enumeration
    return jsonify({
        'message': 'If an account exists with that email, a reset link will be sent.'
    })


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password using token from email.

    Request body:
        token: string (required)
        new_password: string (required)

    Returns:
        Success message
    """
    data = request.json
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    if not data.get('token') or not data.get('new_password'):
        return jsonify({'error': 'Token and new password are required'}), 400

    if len(data['new_password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        email_verification_token=data['token']
    ).first()

    if not member:
        return jsonify({'error': 'Invalid or expired reset token'}), 400

    member.set_password(data['new_password'])
    member.email_verification_token = None  # Clear token after use
    db.session.commit()

    return jsonify({'message': 'Password reset successfully. You can now login.'})


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """
    Verify email using token from verification email.

    Request body:
        token: string (required)

    Returns:
        Success message
    """
    data = request.json
    tenant_id = int(request.headers.get('X-Tenant-ID', 1))

    if not data.get('token'):
        return jsonify({'error': 'Verification token is required'}), 400

    member = Member.query.filter_by(
        tenant_id=tenant_id,
        email_verification_token=data['token']
    ).first()

    if not member:
        return jsonify({'error': 'Invalid verification token'}), 400

    member.email_verified = True
    member.email_verification_token = None
    db.session.commit()

    return jsonify({'message': 'Email verified successfully'})
