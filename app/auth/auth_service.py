"""
Authentication service for user login and session management.
"""
from flask import session
from typing import Optional, Tuple
from app.database.models import Database, User


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def login(self, username: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Authenticate user and create session.
        
        Returns:
            (success: bool, user: User | None, error_message: str | None)
        """
        user = self.db.get_user_by_username(username)
        
        if not user:
            return False, None, "Invalid username or password"
        
        if not user.verify_password(password):
            return False, None, "Invalid username or password"
        
        # Create session
        session['user_id'] = user.user_id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        
        return True, user, None
    
    def logout(self):
        """Clear user session."""
        session.clear()
    
    def get_current_user(self) -> Optional[User]:
        """Get current logged-in user from session."""
        user_id = session.get('user_id')
        if not user_id:
            return None
        
        return self.db.get_user_by_id(user_id)
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return 'user_id' in session
    
    def is_admin(self) -> bool:
        """Check if current user is admin."""
        return session.get('is_admin', False)
    
    def require_admin(self) -> bool:
        """Check if current user is admin. Returns False if not authenticated or not admin."""
        return self.is_authenticated() and self.is_admin()

