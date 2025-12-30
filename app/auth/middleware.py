"""
Authentication middleware for protecting routes.
"""
from functools import wraps
from flask import redirect, url_for, request, jsonify
from app.auth.auth_service import AuthService
from app.database.models import Database


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db = Database()
        auth_service = AuthService(db)
        
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db = Database()
        auth_service = AuthService(db)
        
        if not auth_service.is_authenticated():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))
        
        if not auth_service.is_admin():
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin privileges required'}), 403
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function

