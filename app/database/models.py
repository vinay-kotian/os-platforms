"""
Database models for the application.
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from typing import Optional, List, Dict


class User:
    """User model for authentication."""
    
    def __init__(self, username: str, password_hash: str, is_admin: bool = False, 
                 created_at: Optional[str] = None, user_id: Optional[int] = None):
        self.user_id = user_id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.created_at = created_at or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert user to dictionary."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'is_admin': self.is_admin,
            'created_at': self.created_at
        }
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)


class Database:
    """Database connection and operations."""
    
    def __init__(self, db_path: str = 'app.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, username: str, password: str, is_admin: bool = False) -> Optional[User]:
        """Create a new user. Returns User object or None if username exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Use pbkdf2:sha256 method for better compatibility
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            created_at = datetime.utcnow().isoformat()
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, is_admin, created_at)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, is_admin, created_at))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            return User(username, password_hash, is_admin, created_at, user_id)
        except sqlite3.IntegrityError:
            # Username already exists
            return None
        finally:
            conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, password_hash, is_admin, created_at
            FROM users
            WHERE username = ?
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                username=row['username'],
                password_hash=row['password_hash'],
                is_admin=bool(row['is_admin']),
                created_at=row['created_at'],
                user_id=row['user_id']
            )
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by user_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, password_hash, is_admin, created_at
            FROM users
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                username=row['username'],
                password_hash=row['password_hash'],
                is_admin=bool(row['is_admin']),
                created_at=row['created_at'],
                user_id=row['user_id']
            )
        return None
    
    def get_all_users(self) -> List[User]:
        """Get all users (admin only)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, password_hash, is_admin, created_at
            FROM users
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            User(
                username=row['username'],
                password_hash=row['password_hash'],
                is_admin=bool(row['is_admin']),
                created_at=row['created_at'],
                user_id=row['user_id']
            )
            for row in rows
        ]
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted

