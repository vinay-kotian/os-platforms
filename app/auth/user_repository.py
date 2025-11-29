"""
User repository for database operations
"""
import sqlite3
from datetime import datetime
from typing import Optional
from .models import User

DATABASE_FILE = 'app.db'


class UserRepository:
    """Repository for user data access"""
    
    def __init__(self, db_file: str = DATABASE_FILE):
        self.db_file = db_file
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Ensure users table exists"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login TEXT
                )
            ''')
            
            # Create index on username and email for faster lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_username ON users(username)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_email ON users(email)
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error creating users table: {e}")
            raise
    
    def create_user(self, username: str, email: str, password_hash: str) -> Optional[User]:
        """Create a new user"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
            ''', (username, email, password_hash, now, now))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return self.get_user_by_id(user_id)
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                raise ValueError(f"Username '{username}' already exists")
            elif 'email' in str(e):
                raise ValueError(f"Email '{email}' already exists")
            raise
        except Exception as e:
            print(f"Error creating user: {e}")
            raise
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._row_to_user(row)
            return None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._row_to_user(row)
            return None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._row_to_user(row)
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    
    def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Update user fields"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Build update query dynamically
            allowed_fields = ['username', 'email', 'password_hash', 'is_active', 'last_login']
            updates = []
            values = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)
            
            if not updates:
                conn.close()
                return self.get_user_by_id(user_id)
            
            # Always update updated_at
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            
            conn.commit()
            conn.close()
            
            return self.get_user_by_id(user_id)
        except Exception as e:
            print(f"Error updating user: {e}")
            raise
    
    def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        try:
            self.update_user(user_id, last_login=datetime.now().isoformat())
        except Exception as e:
            print(f"Error updating last login: {e}")
    
    def _row_to_user(self, row) -> User:
        """Convert database row to User object"""
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            is_active=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
            updated_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
            last_login=datetime.fromisoformat(row[7]) if row[7] else None
        )

