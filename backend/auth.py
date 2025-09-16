from functools import wraps
from flask import session, redirect, url_for, request, jsonify


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow either a regular logged-in user or an admin
        if 'user_id' not in session and not session.get('is_admin'):
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('api.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            if request.is_json:
                return jsonify({'error': 'Admin privileges required'}), 403
            return redirect(url_for('api.login'))
        return f(*args, **kwargs)
    return decorated


def admin_or_subadmin_required(f):
    """Decorator to require admin or sub-admin privileges (for plant management)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (session.get('is_admin') or session.get('is_sub_admin')):
            if request.is_json:
                return jsonify({'error': 'Admin or sub-admin privileges required'}), 403
            return redirect(url_for('api.login'))
        return f(*args, **kwargs)
    return decorated


def admin_or_market_required(f):
    """Decorator to require admin or market sub-admin privileges (for marketplace management)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (session.get('is_admin') or session.get('is_market_admin')):
            if request.is_json:
                return jsonify({'error': 'Admin or market sub-admin privileges required'}), 403
            return redirect(url_for('api.login'))
        return f(*args, **kwargs)
    return decorated


def login_user(user=None, admin=False):
    """Log in a user (set session). If admin=True, set admin session instead."""
    session.clear()
    if admin:
        session['user_id'] = 0
        session['username'] = 'admin'
        session['is_admin'] = True
        session['is_sub_admin'] = False
        session['is_market_admin'] = False
    else:
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = False
        role = getattr(user, 'role', '') or ''
        session['is_sub_admin'] = True if role == 'sub_admin' else False
        session['is_market_admin'] = True if role == 'market_sub_admin' else False


def logout_user():
    """Log out user (clear session)"""
    session.clear()


def get_current_user():
    """Get current logged in user (returns None for admin)"""
    from backend.models import User
    if session.get('is_admin'):
        return None
    if 'user_id' in session:
        return User.get_by_username(session['username'])
    return None
