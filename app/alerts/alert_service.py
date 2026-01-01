"""
Alert service for managing price level alerts.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from app.database.models import Database


class AlertService:
    """Service for alert operations."""
    
    def __init__(self, user_id: Optional[int] = None):
        self.db = Database()
        self.user_id = user_id
    
    def create_level_alert(self, user_id: int, exchange: str, symbol: str, price_level: float,
                          ttl_type: str, expires_at: Optional[str] = None) -> Tuple[bool, Optional[int], Optional[str]]:
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
            (success: bool, level_alert_id: Optional[int], error_message: Optional[str])
        """
        # Validate ttl_type
        if ttl_type not in ['intraday', 'longterm']:
            return False, None, "TTL type must be 'intraday' or 'longterm'"
        
        # For intraday alerts, set expiration to end of trading day (3:00 PM IST = 9:30 AM UTC)
        if ttl_type == 'intraday' and not expires_at:
            # Set to 3:00 PM IST (9:30 AM UTC) on current day
            now = datetime.utcnow()
            # If it's past 9:30 AM UTC, set for next day
            if now.hour >= 9 and now.minute >= 30:
                expires_at = now.replace(hour=9, minute=30, second=0, microsecond=0) + timedelta(days=1)
            else:
                expires_at = now.replace(hour=9, minute=30, second=0, microsecond=0)
            expires_at = expires_at.isoformat()
        
        level_alert_id = self.db.create_level_alert(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            price_level=price_level,
            ttl_type=ttl_type,
            expires_at=expires_at
        )
        
        if level_alert_id:
            return True, level_alert_id, None
        else:
            return False, None, "Failed to create level alert"
    
    def get_user_level_alerts(self, user_id: int, active_only: bool = False) -> List[Dict]:
        """Get all level alerts for a user."""
        return self.db.get_user_level_alerts(user_id, active_only)
    
    def get_level_alert(self, level_alert_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """Get a specific level alert."""
        return self.db.get_level_alert(level_alert_id, user_id)
    
    def update_level_alert(self, level_alert_id: int, user_id: int, price_level: Optional[float] = None,
                          ttl_type: Optional[str] = None, expires_at: Optional[str] = None,
                          is_active: Optional[bool] = None) -> Tuple[bool, Optional[str]]:
        """
        Update a level alert.
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        # Validate ttl_type if provided
        if ttl_type is not None and ttl_type not in ['intraday', 'longterm']:
            return False, "TTL type must be 'intraday' or 'longterm'"
        
        success = self.db.update_level_alert(
            level_alert_id=level_alert_id,
            user_id=user_id,
            price_level=price_level,
            ttl_type=ttl_type,
            expires_at=expires_at,
            is_active=is_active
        )
        
        if success:
            return True, None
        else:
            return False, "Level alert not found or update failed"
    
    def delete_level_alert(self, level_alert_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete a level alert.
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        success = self.db.delete_level_alert(level_alert_id, user_id)
        
        if success:
            return True, None
        else:
            return False, "Level alert not found"
    
    def get_active_level_alerts(self) -> List[Dict]:
        """Get all active level alerts across all users."""
        return self.db.get_active_level_alerts()
    
    def mark_level_alert_triggered(self, level_alert_id: int) -> bool:
        """Mark a level alert as triggered."""
        return self.db.mark_level_alert_triggered(level_alert_id)

