"""
User domain models
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User domain model"""
    id: Optional[int]
    username: str
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    def to_dict(self, include_password=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
        if self.last_login:
            data['last_login'] = self.last_login.isoformat() if isinstance(self.last_login, datetime) else self.last_login
        if include_password:
            data['password_hash'] = self.password_hash
        return data


@dataclass
class UserSession:
    """User session model"""
    user_id: int
    session_token: str
    expires_at: datetime
    created_at: datetime

