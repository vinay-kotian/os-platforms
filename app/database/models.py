"""
Database models for the application.
"""
from datetime import datetime, timedelta
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
        
        # Create tre_settings table (TRE configuration per user)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tre_settings (
                tre_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stop_loss_percent REAL DEFAULT 2.0,
                target_percent REAL DEFAULT 5.0,
                trend_lookback_minutes INTEGER DEFAULT 20,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id)
            )
        ''')
        
        # Create oop_settings table (OOP configuration per user)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oop_settings (
                oop_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                paper_trading INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id)
            )
        ''')
        
        # Create trade_signals table (signals generated by TRE)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_signals (
                trade_signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                level_alert_id INTEGER,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                instrument_token TEXT,
                option_type TEXT NOT NULL CHECK(option_type IN ('CALL', 'PUT')),
                strike_price REAL,
                entry_price REAL,
                stop_loss REAL,
                target REAL,
                trend_direction TEXT NOT NULL CHECK(trend_direction IN ('uptrend', 'downtrend')),
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'sent', 'executed', 'closed', 'cancelled')),
                ttl_type TEXT NOT NULL CHECK(ttl_type IN ('intraday', 'longterm')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (level_alert_id) REFERENCES level_alerts(level_alert_id)
            )
        ''')
        
        # Create oop_orders table (GTT orders with OCO)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oop_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trade_signal_id INTEGER,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                instrument_token TEXT,
                option_type TEXT NOT NULL CHECK(option_type IN ('CALL', 'PUT')),
                entry_price REAL NOT NULL,
                stop_loss_price REAL NOT NULL,
                target_price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                order_type TEXT DEFAULT 'GTT' CHECK(order_type IN ('GTT', 'MARKET', 'LIMIT')),
                oco_group_id TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'triggered', 'executed', 'stopped_out', 'target_hit', 'cancelled', 'expired')),
                ttl_type TEXT NOT NULL CHECK(ttl_type IN ('intraday', 'longterm')),
                expires_at TEXT,
                executed_at TEXT,
                executed_price REAL,
                pnl REAL,
                pnl_percent REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (trade_signal_id) REFERENCES trade_signals(trade_signal_id)
            )
        ''')
        
        # Create oop_trades table (executed paper trades)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oop_trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                option_type TEXT NOT NULL CHECK(option_type IN ('CALL', 'PUT')),
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                exit_reason TEXT NOT NULL CHECK(exit_reason IN ('target_hit', 'stop_loss', 'time_based', 'manual')),
                pnl REAL NOT NULL,
                pnl_percent REAL NOT NULL,
                executed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES oop_orders(order_id),
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
        
        alerts = [dict(row) for row in rows]
        
        # Filter out expired intraday alerts (compare in Python for accurate UTC comparison)
        if active_only:
            now_utc = datetime.utcnow()
            filtered_alerts = []
            for alert in alerts:
                # Long-term alerts never expire
                if alert['ttl_type'] == 'longterm':
                    filtered_alerts.append(alert)
                # Intraday alerts expire at expires_at
                elif alert['ttl_type'] == 'intraday':
                    if alert.get('expires_at'):
                        try:
                            expires_at = datetime.fromisoformat(alert['expires_at'])
                            if expires_at > now_utc:
                                filtered_alerts.append(alert)
                        except (ValueError, AttributeError):
                            # If parsing fails, include it (better safe than sorry)
                            filtered_alerts.append(alert)
                    else:
                        # No expiration set, include it
                        filtered_alerts.append(alert)
            return filtered_alerts
        
        return alerts
    
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
        """Get all active level alerts across all users (excluding expired alerts)."""
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
        
        alerts = [dict(row) for row in rows]
        
        # Filter out expired intraday alerts (compare in Python for accurate UTC comparison)
        now_utc = datetime.utcnow()
        filtered_alerts = []
        for alert in alerts:
            # Long-term alerts never expire
            if alert['ttl_type'] == 'longterm':
                filtered_alerts.append(alert)
            # Intraday alerts expire at expires_at
            elif alert['ttl_type'] == 'intraday':
                if alert.get('expires_at'):
                    try:
                        expires_at = datetime.fromisoformat(alert['expires_at'])
                        if expires_at > now_utc:
                            filtered_alerts.append(alert)
                    except (ValueError, AttributeError):
                        # If parsing fails, include it (better safe than sorry)
                        filtered_alerts.append(alert)
                else:
                    # No expiration set, include it
                    filtered_alerts.append(alert)
        
        return filtered_alerts
    
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
    
    # TRE Settings Methods
    def create_or_update_tre_settings(self, user_id: int, stop_loss_percent: float = 2.0,
                                      target_percent: float = 5.0,
                                      trend_lookback_minutes: int = 20,
                                      is_active: bool = True) -> bool:
        """Create or update TRE settings for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        # Check if settings exist
        cursor.execute('SELECT tre_setting_id FROM tre_settings WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            cursor.execute('''
                UPDATE tre_settings
                SET stop_loss_percent = ?, target_percent = ?, trend_lookback_minutes = ?,
                    is_active = ?, updated_at = ?
                WHERE user_id = ?
            ''', (stop_loss_percent, target_percent, trend_lookback_minutes,
                  1 if is_active else 0, now, user_id))
        else:
            # Create new
            cursor.execute('''
                INSERT INTO tre_settings (user_id, stop_loss_percent, target_percent,
                                        trend_lookback_minutes, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, stop_loss_percent, target_percent, trend_lookback_minutes,
                  1 if is_active else 0, now, now))
        
        conn.commit()
        conn.close()
        return True
    
    def get_tre_settings(self, user_id: int) -> Optional[Dict]:
        """Get TRE settings for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tre_setting_id, user_id, stop_loss_percent, target_percent,
                   trend_lookback_minutes, is_active, created_at, updated_at
            FROM tre_settings
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    # Trade Signals Methods
    def create_trade_signal(self, user_id: int, level_alert_id: Optional[int],
                           exchange: str, symbol: str, instrument_token: Optional[str],
                           option_type: str, strike_price: Optional[float],
                           entry_price: float, stop_loss: float, target: float,
                           trend_direction: str, ttl_type: str) -> Optional[int]:
        """Create a new trade signal."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
            INSERT INTO trade_signals (user_id, level_alert_id, exchange, symbol, instrument_token,
                                     option_type, strike_price, entry_price, stop_loss, target,
                                     trend_direction, status, ttl_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        ''', (user_id, level_alert_id, exchange, symbol, instrument_token,
              option_type, strike_price, entry_price, stop_loss, target,
              trend_direction, ttl_type, now, now))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return signal_id
    
    def get_trade_signals(self, user_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict]:
        """Get trade signals, optionally filtered by user_id and status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT trade_signal_id, user_id, level_alert_id, exchange, symbol, instrument_token,
                   option_type, strike_price, entry_price, stop_loss, target, trend_direction,
                   status, ttl_type, created_at, updated_at
            FROM trade_signals
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_trade_signal_status(self, trade_signal_id: int, status: str) -> bool:
        """Update trade signal status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        cursor.execute('''
            UPDATE trade_signals
            SET status = ?, updated_at = ?
            WHERE trade_signal_id = ?
        ''', (status, now, trade_signal_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    # OOP Orders Methods
    def create_oop_order(self, user_id: int, trade_signal_id: Optional[int],
                         exchange: str, symbol: str, instrument_token: Optional[str],
                         option_type: str, entry_price: float, stop_loss_price: float,
                         target_price: float, quantity: int = 1, ttl_type: str = 'intraday',
                         expires_at: Optional[str] = None) -> Optional[int]:
        """Create a new OOP order (GTT with OCO)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow()
        now_str = now.isoformat()
        
        # Generate OCO group ID (same for target and SL orders)
        import uuid
        oco_group_id = str(uuid.uuid4())
        
        # Set expiration for intraday orders (3:00 PM IST = 9:30 AM UTC)
        if ttl_type == 'intraday' and not expires_at:
            expires_at = now.replace(hour=9, minute=30, second=0, microsecond=0)
            if now.hour >= 9 and now.minute >= 30:
                expires_at = expires_at + timedelta(days=1)
            expires_at = expires_at.isoformat()
        
        cursor.execute('''
            INSERT INTO oop_orders (user_id, trade_signal_id, exchange, symbol, instrument_token,
                                   option_type, entry_price, stop_loss_price, target_price, quantity,
                                   order_type, oco_group_id, status, ttl_type, expires_at,
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'GTT', ?, 'pending', ?, ?, ?, ?)
        ''', (user_id, trade_signal_id, exchange, symbol, instrument_token,
              option_type, entry_price, stop_loss_price, target_price, quantity,
              oco_group_id, ttl_type, expires_at, now_str, now_str))
        
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return order_id
    
    def get_oop_orders(self, user_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict]:
        """Get OOP orders, optionally filtered by user_id and status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT order_id, user_id, trade_signal_id, exchange, symbol, instrument_token,
                   option_type, entry_price, stop_loss_price, target_price, quantity,
                   order_type, oco_group_id, status, ttl_type, expires_at,
                   executed_at, executed_price, pnl, pnl_percent, created_at, updated_at
            FROM oop_orders
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_active_oop_orders(self) -> List[Dict]:
        """Get all active OOP orders (pending or active status)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now_utc = datetime.utcnow()
        
        cursor.execute('''
            SELECT order_id, user_id, trade_signal_id, exchange, symbol, instrument_token,
                   option_type, entry_price, stop_loss_price, target_price, quantity,
                   order_type, oco_group_id, status, ttl_type, expires_at,
                   executed_at, executed_price, pnl, pnl_percent, created_at, updated_at
            FROM oop_orders
            WHERE status IN ('pending', 'active')
            AND (ttl_type = 'longterm' OR (ttl_type = 'intraday' AND (expires_at IS NULL OR expires_at > ?)))
            ORDER BY created_at ASC
        ''', (now_utc.isoformat(),))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_oop_order_status(self, order_id: int, status: str, executed_price: Optional[float] = None,
                               pnl: Optional[float] = None, pnl_percent: Optional[float] = None) -> bool:
        """Update OOP order status and execution details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        updates = ['status = ?', 'updated_at = ?']
        params = [status, now]
        
        if executed_price is not None:
            updates.append('executed_price = ?')
            updates.append('executed_at = ?')
            params.append(executed_price)
            params.append(now)
        
        if pnl is not None:
            updates.append('pnl = ?')
            params.append(pnl)
        
        if pnl_percent is not None:
            updates.append('pnl_percent = ?')
            params.append(pnl_percent)
        
        params.append(order_id)
        
        cursor.execute(f'''
            UPDATE oop_orders
            SET {', '.join(updates)}
            WHERE order_id = ?
        ''', params)
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def cancel_oco_orders(self, oco_group_id: str, exclude_order_id: Optional[int] = None) -> int:
        """Cancel all orders in an OCO group except the specified order."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        if exclude_order_id:
            cursor.execute('''
                UPDATE oop_orders
                SET status = 'cancelled', updated_at = ?
                WHERE oco_group_id = ? AND order_id != ? AND status IN ('pending', 'active')
            ''', (now, oco_group_id, exclude_order_id))
        else:
            cursor.execute('''
                UPDATE oop_orders
                SET status = 'cancelled', updated_at = ?
                WHERE oco_group_id = ? AND status IN ('pending', 'active')
            ''', (now, oco_group_id))
        
        cancelled = cursor.rowcount
        conn.commit()
        conn.close()
        
        return cancelled
    
    # OOP Trades Methods
    def create_oop_trade(self, order_id: int, user_id: int, exchange: str, symbol: str,
                        option_type: str, entry_price: float, exit_price: float,
                        quantity: int, exit_reason: str, pnl: float, pnl_percent: float) -> Optional[int]:
        """Create a new executed paper trade record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
            INSERT INTO oop_trades (order_id, user_id, exchange, symbol, option_type,
                                   entry_price, exit_price, quantity, exit_reason,
                                   pnl, pnl_percent, executed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, user_id, exchange, symbol, option_type,
              entry_price, exit_price, quantity, exit_reason,
              pnl, pnl_percent, now, now))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return trade_id
    
    def get_oop_trades(self, user_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get OOP trades, optionally filtered by user_id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT trade_id, order_id, user_id, exchange, symbol, option_type,
                   entry_price, exit_price, quantity, exit_reason,
                   pnl, pnl_percent, executed_at, created_at
            FROM oop_trades
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY executed_at DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # OOP Settings Methods
    def create_or_update_oop_settings(self, user_id: int, paper_trading: bool = True,
                                      is_active: bool = True) -> bool:
        """Create or update OOP settings for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        # Check if settings exist
        cursor.execute('SELECT oop_setting_id FROM oop_settings WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            cursor.execute('''
                UPDATE oop_settings
                SET paper_trading = ?, is_active = ?, updated_at = ?
                WHERE user_id = ?
            ''', (1 if paper_trading else 0, 1 if is_active else 0, now, user_id))
        else:
            # Create new
            cursor.execute('''
                INSERT INTO oop_settings (user_id, paper_trading, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 1 if paper_trading else 0, 1 if is_active else 0, now, now))
        
        conn.commit()
        conn.close()
        return True
    
    def get_oop_settings(self, user_id: int) -> Optional[Dict]:
        """Get OOP settings for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT oop_setting_id, user_id, paper_trading, is_active, created_at, updated_at
            FROM oop_settings
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None

