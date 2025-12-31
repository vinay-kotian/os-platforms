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
        
        # Create subscriptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                instrument_token TEXT,
                tradingsymbol TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, exchange, symbol)
            )
        ''')
        
        # Create zerodha_keys table (admin only)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zerodha_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT NOT NULL,
                api_secret TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create zerodha_sessions table for access tokens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zerodha_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                access_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id)
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
    
    # Subscription methods
    def add_subscription(self, user_id: int, exchange: str, symbol: str, 
                        instrument_token: Optional[str] = None, 
                        tradingsymbol: Optional[str] = None) -> Optional[int]:
        """Add a subscription for a user. Returns subscription_id or None if already exists."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            created_at = datetime.utcnow().isoformat()
            cursor.execute('''
                INSERT INTO subscriptions (user_id, exchange, symbol, instrument_token, tradingsymbol, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, exchange, symbol, instrument_token, tradingsymbol, created_at))
            
            subscription_id = cursor.lastrowid
            conn.commit()
            return subscription_id
        except sqlite3.IntegrityError:
            # Subscription already exists
            return None
        finally:
            conn.close()
    
    def remove_subscription(self, user_id: int, exchange: str, symbol: str) -> bool:
        """Remove a subscription for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM subscriptions 
            WHERE user_id = ? AND exchange = ? AND symbol = ?
        ''', (user_id, exchange, symbol))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT subscription_id, exchange, symbol, instrument_token, tradingsymbol, created_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_subscriptions(self) -> List[Dict]:
        """Get all subscriptions across all users."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT subscription_id, user_id, exchange, symbol, instrument_token, tradingsymbol, created_at
            FROM subscriptions
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # Zerodha keys methods (admin only)
    def set_zerodha_keys(self, api_key: str, api_secret: str) -> bool:
        """Set Zerodha API keys. Only one active key pair allowed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Deactivate all existing keys
        cursor.execute('UPDATE zerodha_keys SET is_active = 0')
        
        # Insert new keys
        created_at = datetime.utcnow().isoformat()
        cursor.execute('''
            INSERT INTO zerodha_keys (api_key, api_secret, is_active, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?)
        ''', (api_key, api_secret, created_at, created_at))
        
        conn.commit()
        conn.close()
        return True
    
    def get_zerodha_keys(self) -> Optional[Dict]:
        """Get active Zerodha API keys."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT api_key, api_secret
            FROM zerodha_keys
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {'api_key': row['api_key'], 'api_secret': row['api_secret']}
        return None
    
    # Zerodha session/access token methods
    def set_zerodha_session(self, user_id: int, access_token: str, expires_at: Optional[str] = None) -> bool:
        """Store Zerodha access token for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        created_at = datetime.utcnow().isoformat()
        
        # Use INSERT OR REPLACE to update if exists
        cursor.execute('''
            INSERT OR REPLACE INTO zerodha_sessions (user_id, access_token, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, access_token, created_at, expires_at))
        
        conn.commit()
        conn.close()
        return True
    
    def get_zerodha_session(self, user_id: int) -> Optional[Dict]:
        """Get Zerodha access token for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT access_token, created_at, expires_at
            FROM zerodha_sessions
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'access_token': row['access_token'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at']
            }
        return None
    
    def delete_zerodha_session(self, user_id: int) -> bool:
        """Delete Zerodha session for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM zerodha_sessions WHERE user_id = ?', (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted

