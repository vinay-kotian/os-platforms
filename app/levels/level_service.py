"""
Level service for business logic
"""
from typing import Optional, List, Dict, Tuple
from .level_repository import LevelRepository
from .models import Level, LevelType


class LevelService:
    """Service for level operations"""
    
    def __init__(self, repository: Optional[LevelRepository] = None):
        self.repository = repository or LevelRepository()
    
    def save_level(self, user_id: str, index_type: str, level_value: float,
                  level_uuid: Optional[str] = None, stock_symbol: Optional[str] = None,
                  stock_exchange: Optional[str] = None, stop_loss: Optional[float] = None,
                  target_percentage: Optional[float] = None, expiry_type: str = "today",
                  expiry_date: Optional[str] = None) -> Tuple[bool, Optional[Level], Optional[str]]:
        """
        Save or update a level
        
        Returns:
            (success: bool, level: Level or None, error_message: str or None)
        """
        # Validate input
        if not index_type:
            return False, None, "index_type is required"
        
        if not isinstance(level_value, (int, float)) or level_value <= 0:
            return False, None, "level_value must be a positive number"
        
        # Validate stop_loss and target_percentage if provided
        if stop_loss is not None:
            if not isinstance(stop_loss, (int, float)) or stop_loss < 0 or stop_loss > 100:
                return False, None, "stop_loss must be between 0 and 100"
        
        if target_percentage is not None:
            if not isinstance(target_percentage, (int, float)) or target_percentage < 0:
                return False, None, "target_percentage must be a positive number"
        
        # Validate expiry_type
        if expiry_type not in ["today", "persistent", "expiry_date"]:
            return False, None, "expiry_type must be 'today', 'persistent', or 'expiry_date'"
        
        # Validate expiry_date if expiry_type is 'expiry_date'
        if expiry_type == "expiry_date":
            if not expiry_date:
                return False, None, "expiry_date is required when expiry_type is 'expiry_date'"
            try:
                from datetime import datetime
                expiry = datetime.fromisoformat(expiry_date).date() if isinstance(expiry_date, str) else expiry_date
                today = datetime.now().date()
                if expiry < today:
                    return False, None, "expiry_date cannot be in the past"
            except ValueError:
                return False, None, "expiry_date must be a valid ISO date string (YYYY-MM-DD)"
        
        # Parse stock symbol if index_type contains it
        if ':' in index_type and not stock_symbol:
            parts = index_type.split(':')
            if len(parts) == 2:
                stock_exchange = parts[0]
                stock_symbol = index_type
                # Keep index_type as is for backward compatibility
        
        # Update existing level or create new one
        if level_uuid:
            level = self.repository.update_level(
                level_uuid, user_id, level_value, stock_symbol, stock_exchange,
                stop_loss, target_percentage, expiry_type, expiry_date
            )
            if level:
                return True, level, None
            else:
                return False, None, "Level not found or update failed"
        else:
            level = self.repository.create_level(
                user_id, index_type, level_value, stock_symbol, stock_exchange,
                stop_loss, target_percentage, expiry_type, expiry_date
            )
            if level:
                return True, level, None
            else:
                return False, None, "Failed to create level"
    
    def get_levels(self, user_id: str, index_type: Optional[str] = None,
                   today_only: bool = False, stock_symbol: Optional[str] = None,
                   grouped: bool = False, active_only: bool = True) -> Dict[str, List[Level]]:
        """
        Get levels for a user
        
        Args:
            user_id: User ID
            index_type: Optional filter by index type
            today_only: Only return levels created today
            stock_symbol: Optional filter by stock symbol
            grouped: If True, return grouped by instrument
            active_only: If True, only return active (non-expired) levels
        
        Returns:
            Dictionary mapping instrument keys to lists of levels
        """
        if grouped:
            levels = self.repository.get_levels(user_id, index_type, today_only, stock_symbol, active_only)
            print(f"DEBUG: get_levels - user_id={user_id}, stock_symbol={stock_symbol}, found {len(levels)} levels")
            # Group by instrument
            grouped_levels = {}
            for level in levels:
                key = level.get_instrument_key()
                if key not in grouped_levels:
                    grouped_levels[key] = []
                grouped_levels[key].append(level)
                print(f"DEBUG: Grouped level {level.uuid} under key '{key}' (index_type={level.index_type}, stock_symbol={level.stock_symbol})")
            return grouped_levels
        else:
            levels = self.repository.get_levels(user_id, index_type, today_only, stock_symbol, active_only)
            # Convert to grouped format for consistency
            grouped_levels = {}
            for level in levels:
                key = level.get_instrument_key()
                if key not in grouped_levels:
                    grouped_levels[key] = []
                grouped_levels[key].append(level)
            return grouped_levels
    
    def get_level(self, level_uuid: str, user_id: str) -> Optional[Level]:
        """Get a single level by UUID"""
        return self.repository.get_level_by_uuid(level_uuid, user_id)
    
    def delete_level(self, level_uuid: str, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a level
        
        Returns:
            (success: bool, error_message: str or None)
        """
        success = self.repository.delete_level(level_uuid, user_id)
        if success:
            return True, None
        else:
            return False, "Level not found or delete failed"
    
    def clear_levels(self, user_id: str, index_type: Optional[str] = None,
                    today_only: bool = False, stock_symbol: Optional[str] = None) -> Tuple[int, Optional[str]]:
        """
        Clear levels matching filters
        
        Returns:
            (deleted_count: int, error_message: str or None)
        """
        try:
            count = self.repository.clear_levels(user_id, index_type, today_only, stock_symbol)
            return count, None
        except Exception as e:
            return 0, str(e)
    
    def validate_level(self, level_value: float, current_price: Optional[float] = None,
                      stop_loss: Optional[float] = None, target_percentage: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate level parameters
        
        Returns:
            (is_valid: bool, error_message: str or None)
        """
        if level_value <= 0:
            return False, "Level value must be positive"
        
        if stop_loss is not None:
            if stop_loss < 0 or stop_loss > 100:
                return False, "Stop loss must be between 0 and 100 percent"
            
            stop_loss_price = level_value * (1 - stop_loss / 100)
            if current_price and stop_loss_price > current_price:
                return False, "Stop loss price cannot be above current price"
        
        if target_percentage is not None:
            if target_percentage < 0:
                return False, "Target percentage must be positive"
            
            if stop_loss and target_percentage <= stop_loss:
                return False, "Target percentage should be greater than stop loss percentage"
        
        return True, None

