"""
Authentication module for user management and login
"""
from .auth_service import AuthService
from .user_repository import UserRepository
from .models import User
from .helpers import get_current_user_id, get_current_username, is_authenticated
from .middleware import login_required

__all__ = [
    'AuthService', 
    'UserRepository', 
    'User',
    'get_current_user_id',
    'get_current_username',
    'is_authenticated',
    'login_required'
]

