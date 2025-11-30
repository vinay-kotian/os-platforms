"""
Level repository for database operations
"""
import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from .models import Level

DATABASE_FILE = 'app.db'


class LevelRepository:
    """Repository for level data access"""
    
    def __init__(self, db_file: str = DATABASE_FILE):
        self.db_file = db_file
    
    def create_level(self, user_id: str, index_type: str, level_value: float,
                    stock_symbol: Optional[str] = None, stock_exchange: Optional[str] = None,
                    stop_loss: Optional[float] = None, target_percentage: Optional[float] = None,
                    expiry_type: str = "today", expiry_date: Optional[str] = None) -> Optional[Level]:
        """Create a new level"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Ensure expiry columns exist
            self._ensure_expiry_columns(cursor)
            
            level_uuid = str(uuid.uuid4())
            current_time = datetime.now().isoformat()
            current_date = datetime.now().date().isoformat()
            
            cursor.execute('''
                INSERT INTO level 
                (uuid, user_id, index_type, level_value, created_at, updated_at, created_date, 
                 stock_symbol, stock_exchange, stop_loss, target_percentage, expiry_type, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (level_uuid, user_id, index_type, level_value, current_time, current_time, current_date,
                  stock_symbol, stock_exchange, stop_loss, target_percentage, expiry_type, expiry_date))
            
            conn.commit()
            conn.close()
            
            return self.get_level_by_uuid(level_uuid, user_id)
        except Exception as e:
            print(f"Error creating level: {e}")
            return None
    
    def _ensure_expiry_columns(self, cursor):
        """Ensure expiry columns exist in database"""
        try:
            cursor.execute('ALTER TABLE level ADD COLUMN expiry_type TEXT DEFAULT "today"')
        except:
            pass  # Column already exists
        try:
            cursor.execute('ALTER TABLE level ADD COLUMN expiry_date TEXT')
        except:
            pass  # Column already exists
    
    def update_level(self, level_uuid: str, user_id: str, level_value: Optional[float] = None,
                    stock_symbol: Optional[str] = None, stock_exchange: Optional[str] = None,
                    stop_loss: Optional[float] = None, target_percentage: Optional[float] = None,
                    expiry_type: Optional[str] = None, expiry_date: Optional[str] = None) -> Optional[Level]:
        """Update an existing level"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Ensure expiry columns exist
            self._ensure_expiry_columns(cursor)
            
            # Build update query dynamically
            updates = []
            params = []
            
            if level_value is not None:
                updates.append("level_value = ?")
                params.append(level_value)
            
            if stock_symbol is not None:
                updates.append("stock_symbol = ?")
                params.append(stock_symbol)
            
            if stock_exchange is not None:
                updates.append("stock_exchange = ?")
                params.append(stock_exchange)
            
            if stop_loss is not None:
                updates.append("stop_loss = ?")
                params.append(stop_loss)
            
            if target_percentage is not None:
                updates.append("target_percentage = ?")
                params.append(target_percentage)
            
            if expiry_type is not None:
                updates.append("expiry_type = ?")
                params.append(expiry_type)
            
            if expiry_date is not None:
                updates.append("expiry_date = ?")
                params.append(expiry_date)
            
            if not updates:
                conn.close()
                return self.get_level_by_uuid(level_uuid, user_id)
            
            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.extend([level_uuid, user_id])
            
            query = f"UPDATE level SET {', '.join(updates)} WHERE uuid = ? AND user_id = ?"
            cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            
            return self.get_level_by_uuid(level_uuid, user_id)
        except Exception as e:
            print(f"Error updating level: {e}")
            return None
    
    def get_level_by_uuid(self, level_uuid: str, user_id: str) -> Optional[Level]:
        """Get a level by UUID"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Ensure expiry columns exist
            self._ensure_expiry_columns(cursor)
            
            cursor.execute('''
                SELECT uuid, user_id, index_type, level_value, created_at, updated_at, created_date,
                       stock_symbol, stock_exchange, stop_loss, target_percentage, expiry_type, expiry_date
                FROM level
                WHERE uuid = ? AND user_id = ?
            ''', (level_uuid, user_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return self._row_to_level(row)
            return None
        except Exception as e:
            print(f"Error getting level by UUID: {e}")
            return None
    
    def get_levels(self, user_id: str, index_type: Optional[str] = None,
                   today_only: bool = False, stock_symbol: Optional[str] = None,
                   active_only: bool = True) -> List[Level]:
        """Get all levels for a user with optional filters"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Ensure expiry columns exist
            self._ensure_expiry_columns(cursor)
            
            today = datetime.now().date().isoformat()
            
            # Build query based on filters
            query = 'SELECT uuid, user_id, index_type, level_value, created_at, updated_at, created_date, stock_symbol, stock_exchange, stop_loss, target_percentage, expiry_type, expiry_date FROM level WHERE user_id = ?'
            params = [user_id]
            
            if stock_symbol:
                query += ' AND stock_symbol = ?'
                params.append(stock_symbol)
            
            if index_type and not stock_symbol:
                query += ' AND index_type = ?'
                params.append(index_type)
            
            if today_only:
                query += ' AND created_date = ?'
                params.append(today)
            
            # Filter expired levels if active_only is True
            if active_only:
                # Add conditions to exclude expired levels
                # Persistent levels: expiry_type = 'persistent'
                # Today levels: created_date = today
                # Expiry date levels: expiry_date >= today or expiry_date IS NULL
                query += ''' AND (
                    expiry_type = 'persistent' OR
                    (expiry_type = 'today' AND created_date = ?) OR
                    (expiry_type = 'expiry_date' AND (expiry_date >= ? OR expiry_date IS NULL))
                )'''
                params.extend([today, today])
            
            query += ' ORDER BY index_type, level_value DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            levels = [self._row_to_level(row) for row in rows]
            
            # Additional client-side filtering for active levels (more accurate)
            if active_only:
                levels = [level for level in levels if level.is_active()]
            
            return levels
        except Exception as e:
            print(f"Error getting levels: {e}")
            return []
    
    def get_levels_grouped(self, user_id: str, index_type: Optional[str] = None,
                          today_only: bool = False, stock_symbol: Optional[str] = None,
                          active_only: bool = True) -> Dict[str, List[Level]]:
        """Get levels grouped by instrument"""
        levels = self.get_levels(user_id, index_type, today_only, stock_symbol, active_only)
        
        grouped = {}
        for level in levels:
            key = level.get_instrument_key()
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(level)
        
        return grouped
    
    def delete_level(self, level_uuid: str, user_id: str) -> bool:
        """Delete a level"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM level WHERE uuid = ? AND user_id = ?', (level_uuid, user_id))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return deleted
        except Exception as e:
            print(f"Error deleting level: {e}")
            return False
    
    def clear_levels(self, user_id: str, index_type: Optional[str] = None,
                     today_only: bool = False, stock_symbol: Optional[str] = None) -> int:
        """Clear levels matching filters"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            query = 'DELETE FROM level WHERE user_id = ?'
            params = [user_id]
            
            if stock_symbol:
                query += ' AND stock_symbol = ?'
                params.append(stock_symbol)
            
            if index_type and not stock_symbol:
                query += ' AND index_type = ?'
                params.append(index_type)
            
            if today_only:
                query += ' AND created_date = ?'
                params.append(today)
            
            cursor.execute(query, params)
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return deleted_count
        except Exception as e:
            print(f"Error clearing levels: {e}")
            return 0
    
    def _row_to_level(self, row) -> Level:
        """Convert database row to Level object"""
        # Handle rows with or without expiry columns (backward compatibility)
        expiry_type = row[11] if len(row) > 11 else "today"
        expiry_date = row[12] if len(row) > 12 else None
        
        return Level(
            uuid=row[0],
            user_id=row[1],
            index_type=row[2],
            level_value=row[3],
            created_at=datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
            updated_at=datetime.fromisoformat(row[5]) if isinstance(row[5], str) else row[5],
            created_date=row[6],
            stock_symbol=row[7] if len(row) > 7 else None,
            stock_exchange=row[8] if len(row) > 8 else None,
            stop_loss=row[9] if len(row) > 9 else None,
            target_percentage=row[10] if len(row) > 10 else None,
            expiry_type=expiry_type,
            expiry_date=expiry_date
        )

