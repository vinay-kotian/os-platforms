"""
Authentication middleware for protecting routes.
"""
from functools import wraps
from flask import redirect, url_for, request, jsonify, flash
from app.auth.auth_service import AuthService
from app.database.models import Database


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            db = Database()
            auth_service = AuthService(db)
            
            if not auth_service.is_authenticated():
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        except Exception as e:
            import logging
            logging.error(f"Error in login_required middleware: {e}", exc_info=True)
            # Ensure we always return a proper response
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Internal server error'}), 500
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
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
        except Exception as e:
            import logging
            logging.error(f"Error in login_required middleware: {e}", exc_info=True)
            # Ensure we always return a proper response
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Internal server error'}), 500
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    return decorated_function

