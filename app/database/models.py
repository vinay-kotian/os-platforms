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
        
        # Create level_alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS level_alerts (
                level_alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price_level REAL NOT NULL,
                ttl_type TEXT NOT NULL CHECK(ttl_type IN ('intraday', 'longterm')),
                expires_at TEXT,
                is_active INTEGER DEFAULT 1,
                is_triggered INTEGER DEFAULT 0,
                triggered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
    
    # Level Alert methods
    def create_level_alert(self, user_id: int, exchange: str, symbol: str, price_level: float,
                          ttl_type: str, expires_at: Optional[str] = None) -> Optional[int]:
        """
        Create a new level alert.
        
        Args:
            user_id: User ID
            exchange: Exchange (NSE, BSE, etc.)
            symbol: Trading symbol
            price_level: Price level to trigger alert
            ttl_type: 'intraday' or 'longterm'
            expires_at: Optional expiration datetime (for intraday alerts)
        
        Returns:
            Level Alert ID or None if creation failed
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            created_at = datetime.utcnow().isoformat()
            updated_at = created_at
            
            cursor.execute('''
                INSERT INTO level_alerts (user_id, exchange, symbol, price_level, 
                                         ttl_type, expires_at, is_active, is_triggered, 
                                         created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
            ''', (user_id, exchange, symbol, price_level, ttl_type, 
                  expires_at, created_at, updated_at))
            
            level_alert_id = cursor.lastrowid
            conn.commit()
            return level_alert_id
        except Exception as e:
            print(f"Error creating level alert: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_level_alerts(self, user_id: int, active_only: bool = False) -> List[Dict]:
        """Get all level alerts for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT level_alert_id, exchange, symbol, price_level, ttl_type,
                   expires_at, is_active, is_triggered, triggered_at, created_at, updated_at
            FROM level_alerts
            WHERE user_id = ?
        '''
        
        if active_only:
            query += ' AND is_active = 1'
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_level_alert(self, level_alert_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """Get a specific level alert by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT level_alert_id, user_id, exchange, symbol, price_level,
                       ttl_type, expires_at, is_active, is_triggered, triggered_at,
                       created_at, updated_at
                FROM level_alerts
                WHERE level_alert_id = ? AND user_id = ?
            ''', (level_alert_id, user_id))
        else:
            cursor.execute('''
                SELECT level_alert_id, user_id, exchange, symbol, price_level,
                       ttl_type, expires_at, is_active, is_triggered, triggered_at,
                       created_at, updated_at
                FROM level_alerts
                WHERE level_alert_id = ?
            ''', (level_alert_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_level_alert(self, level_alert_id: int, user_id: int, price_level: Optional[float] = None,
                          ttl_type: Optional[str] = None, expires_at: Optional[str] = None,
                          is_active: Optional[bool] = None) -> bool:
        """Update a level alert."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if price_level is not None:
            updates.append('price_level = ?')
            params.append(price_level)
        
        if ttl_type is not None:
            updates.append('ttl_type = ?')
            params.append(ttl_type)
        
        if expires_at is not None:
            updates.append('expires_at = ?')
            params.append(expires_at)
        
        if is_active is not None:
            updates.append('is_active = ?')
            params.append(1 if is_active else 0)
        
        if not updates:
            conn.close()
            return False
        
        updates.append('updated_at = ?')
        params.append(datetime.utcnow().isoformat())
        params.extend([level_alert_id, user_id])
        
        query = f'''
            UPDATE level_alerts
            SET {', '.join(updates)}
            WHERE level_alert_id = ? AND user_id = ?
        '''
        
        cursor.execute(query, params)
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def delete_level_alert(self, level_alert_id: int, user_id: int) -> bool:
        """Delete a level alert."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM level_alerts WHERE level_alert_id = ? AND user_id = ?', (level_alert_id, user_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_active_level_alerts(self) -> List[Dict]:
        """Get all active level alerts across all users."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT level_alert_id, user_id, exchange, symbol, price_level,
                   ttl_type, expires_at, is_active, is_triggered, triggered_at,
                   created_at, updated_at
            FROM level_alerts
            WHERE is_active = 1 AND is_triggered = 0
            ORDER BY created_at ASC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def mark_level_alert_triggered(self, level_alert_id: int) -> bool:
        """Mark a level alert as triggered."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        triggered_at = datetime.utcnow().isoformat()
        cursor.execute('''
            UPDATE level_alerts
            SET is_triggered = 1, triggered_at = ?, is_active = 0
            WHERE level_alert_id = ?
        ''', (triggered_at, level_alert_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated

