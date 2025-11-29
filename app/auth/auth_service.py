"""
Authentication service for user login and registration
"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Tuple
from .user_repository import UserRepository
from .models import User


class AuthService:
    """Service for authentication operations"""
    
    def __init__(self, user_repository: UserRepository = None):
        self.user_repository = user_repository or UserRepository()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt"""
        # Generate a random salt
        salt = secrets.token_hex(16)
        # Hash password with salt
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        # Store as salt:hash
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a hash"""
        try:
            salt, stored_hash = password_hash.split(':')
            password_hash_to_check = hashlib.sha256((password + salt).encode()).hexdigest()
            return password_hash_to_check == stored_hash
        except ValueError:
            # Invalid hash format
            return False
    
    def register_user(self, username: str, email: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Register a new user
        
        Returns:
            (success: bool, user: User or None, error_message: str or None)
        """
        # Validate input
        if not username or len(username) < 3:
            return False, None, "Username must be at least 3 characters"
        
        if not email or '@' not in email:
            return False, None, "Invalid email address"
        
        if not password or len(password) < 6:
            return False, None, "Password must be at least 6 characters"
        
        # Check if user already exists
        if self.user_repository.get_user_by_username(username):
            return False, None, "Username already exists"
        
        if self.user_repository.get_user_by_email(email):
            return False, None, "Email already registered"
        
        # Hash password
        password_hash = self.hash_password(password)
        
        # Create user
        try:
            user = self.user_repository.create_user(username, email, password_hash)
            return True, user, None
        except ValueError as e:
            return False, None, str(e)
        except Exception as e:
            return False, None, f"Error creating user: {str(e)}"
    
    def login_user(self, username: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Authenticate a user
        
        Returns:
            (success: bool, user: User or None, error_message: str or None)
        """
        if not username or not password:
            return False, None, "Username and password are required"
        
        # Get user by username
        user = self.user_repository.get_user_by_username(username)
        
        if not user:
            return False, None, "Invalid username or password"
        
        if not user.is_active:
            return False, None, "Account is inactive"
        
        # Verify password
        if not self.verify_password(password, user.password_hash):
            return False, None, "Invalid username or password"
        
        # Update last login
        self.user_repository.update_last_login(user.id)
        
        return True, user, None
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """Change user password"""
        if not new_password or len(new_password) < 6:
            return False, "New password must be at least 6 characters"
        
        user = self.user_repository.get_user_by_id(user_id)
        if not user:
            return False, "User not found"
        
        # Verify old password
        if not self.verify_password(old_password, user.password_hash):
            return False, "Current password is incorrect"
        
        # Hash new password
        new_password_hash = self.hash_password(new_password)
        
        # Update user
        try:
            self.user_repository.update_user(user_id, password_hash=new_password_hash)
            return True, None
        except Exception as e:
            return False, f"Error changing password: {str(e)}"
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.user_repository.get_user_by_id(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.user_repository.get_user_by_username(username)

