"""
Authentication middleware for protecting routes
"""
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, has_request_context


def login_required(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not has_request_context() or 'user_id' not in session:
            if request.is_json or (has_request_context() and request.path.startswith('/api/')):
                return jsonify({'error': 'Authentication required', 'success': False}), 401
            else:
                return redirect(url_for('auth.login', next=request.url if has_request_context() else None))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user_id():
    """
    Get current logged-in user ID from session.
    Falls back to 'default_user' if not in request context or not logged in.
    """
    if has_request_context():
        user_id = session.get('user_id')
        if user_id:
            return user_id
    
    # Fallback for background threads or non-request contexts
    return 'default_user'


def get_current_username():
    """Get current logged-in username from session"""
    if has_request_context():
        return session.get('username')
    return None


def is_authenticated():
    """Check if user is authenticated"""
    if has_request_context():
        return 'user_id' in session
    return False

