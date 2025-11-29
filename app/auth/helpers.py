"""
Helper functions for authentication
"""
from flask import session, has_request_context


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

