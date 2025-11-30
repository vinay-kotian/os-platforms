"""
Level domain models
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class LevelType(Enum):
    """Type of level/instrument"""
    NIFTY_50 = "NIFTY_50"
    BANK_NIFTY = "BANK_NIFTY"
    STOCK = "STOCK"
    CUSTOM = "CUSTOM"


class ExpiryType(Enum):
    """Type of level expiry - determines how long the level should be considered/active"""
    TODAY = "today"  # Level considered only for today (expires at midnight)
    PERSISTENT = "persistent"  # Level considered indefinitely (never expires)
    EXPIRY_DATE = "expiry_date"  # Level considered until specific date (expires on that date)


@dataclass
class Level:
    """Trading level model"""
    uuid: Optional[str]
    user_id: str
    index_type: str  # 'BANK_NIFTY', 'NIFTY_50', or stock symbol
    level_value: float  # Entry price
    created_at: datetime
    updated_at: datetime
    created_date: str  # Date for daily refresh
    stock_symbol: Optional[str] = None  # For custom stocks: 'EXCHANGE:SYMBOL'
    stock_exchange: Optional[str] = None  # Exchange name
    stop_loss: Optional[float] = None  # Stop loss percentage (e.g., 2.0 for 2%)
    target_percentage: Optional[float] = None  # Target percentage (e.g., 2.5 for 2.5%)
    expiry_type: str = "today"  # 'today', 'persistent', or 'expiry_date' - determines how long level is considered
    expiry_date: Optional[str] = None  # ISO date string (YYYY-MM-DD) - level considered until this date (for expiry_type='expiry_date')
    
    def get_level_type(self) -> LevelType:
        """Determine the type of level"""
        if self.index_type == 'NIFTY_50':
            return LevelType.NIFTY_50
        elif self.index_type == 'BANK_NIFTY':
            return LevelType.BANK_NIFTY
        elif self.stock_symbol:
            return LevelType.STOCK
        else:
            return LevelType.CUSTOM
    
    def get_instrument_key(self) -> str:
        """Get unique key for this instrument"""
        if self.stock_symbol:
            return self.stock_symbol
        return self.index_type
    
    def calculate_stop_loss_price(self) -> Optional[float]:
        """Calculate absolute stop loss price"""
        if self.stop_loss is None:
            return None
        # Stop loss is percentage below entry
        return self.level_value * (1 - self.stop_loss / 100)
    
    def calculate_target_price(self) -> Optional[float]:
        """Calculate absolute target price"""
        if self.target_percentage is None:
            return None
        # Target is percentage above entry
        return self.level_value * (1 + self.target_percentage / 100)
    
    def is_active(self, check_date: Optional[datetime] = None) -> bool:
        """
        Check if level should still be considered based on expiry
        
        Args:
            check_date: Date to check against (defaults to today)
        
        Returns:
            True if level should be considered, False if expired/not applicable
        """
        if check_date is None:
            check_date = datetime.now().date()
        elif isinstance(check_date, datetime):
            check_date = check_date.date()
        
        if self.expiry_type == "persistent":
            return True
        elif self.expiry_type == "today":
            # Check if created_date is today
            try:
                created_date = datetime.fromisoformat(self.created_date).date() if isinstance(self.created_date, str) else self.created_date
                return created_date == check_date
            except:
                return True  # If we can't parse, assume active
        elif self.expiry_type == "expiry_date" and self.expiry_date:
            # Check if expiry_date is in the future
            try:
                expiry = datetime.fromisoformat(self.expiry_date).date() if isinstance(self.expiry_date, str) else self.expiry_date
                return check_date <= expiry
            except:
                return True  # If we can't parse, assume active
        
        return True  # Default to active if expiry_type is unknown
    
    def get_expiry_info(self) -> dict:
        """Get expiry information - how long this level should be considered"""
        if self.expiry_type == "persistent":
            return {
                'expiry_type': 'persistent',
                'expires': False,
                'expiry_date': None,
                'description': 'Level considered indefinitely (never expires)',
                'consideration_period': 'Indefinite'
            }
        elif self.expiry_type == "today":
            return {
                'expiry_type': 'today',
                'expires': True,
                'expiry_date': self.created_date,
                'description': f'Level considered only for {self.created_date} (expires at midnight)',
                'consideration_period': f'Today ({self.created_date})'
            }
        elif self.expiry_type == "expiry_date" and self.expiry_date:
            is_expired = not self.is_active()
            return {
                'expiry_type': 'expiry_date',
                'expires': True,
                'expiry_date': self.expiry_date,
                'is_expired': is_expired,
                'description': f'Level considered until {self.expiry_date}' + (' (EXPIRED - no longer considered)' if is_expired else ''),
                'consideration_period': f'Until {self.expiry_date}' + (' (EXPIRED)' if is_expired else '')
            }
        
        return {
            'expiry_type': self.expiry_type,
            'expires': False,
            'expiry_date': None,
            'description': 'Unknown expiry type',
            'consideration_period': 'Unknown'
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        expiry_info = self.get_expiry_info()
        return {
            'uuid': self.uuid,
            'user_id': self.user_id,
            'index_type': self.index_type,
            'level_value': self.level_value,
            'value': self.level_value,  # Alias for frontend compatibility
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
            'created_date': self.created_date,
            'stock_symbol': self.stock_symbol,
            'stock_exchange': self.stock_exchange,
            'stop_loss': self.stop_loss,
            'target_percentage': self.target_percentage,
            'stop_loss_price': self.calculate_stop_loss_price(),
            'target_price': self.calculate_target_price(),
            'instrument_key': self.get_instrument_key(),
            'level_type': self.get_level_type().value,
            'expiry_type': self.expiry_type,
            'expiry_date': self.expiry_date,
            'is_active': self.is_active(),
            'expiry_info': expiry_info
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Level':
        """Create Level from dictionary"""
        return cls(
            uuid=data.get('uuid'),
            user_id=data.get('user_id'),
            index_type=data.get('index_type'),
            level_value=data.get('level_value'),
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data.get('created_at'), str) else data.get('created_at'),
            updated_at=datetime.fromisoformat(data['updated_at']) if isinstance(data.get('updated_at'), str) else data.get('updated_at'),
            created_date=data.get('created_date'),
            stock_symbol=data.get('stock_symbol'),
            stock_exchange=data.get('stock_exchange'),
            stop_loss=data.get('stop_loss'),
            target_percentage=data.get('target_percentage'),
            expiry_type=data.get('expiry_type', 'today'),
            expiry_date=data.get('expiry_date')
        )

