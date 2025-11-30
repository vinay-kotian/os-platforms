"""
Price domain models
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class PriceData:
    """Price data model for an instrument"""
    instrument: str  # e.g., 'NIFTY 50', 'NIFTY BANK'
    last_price: float
    change: float
    change_percent: float
    timestamp: datetime
    previous_close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.instrument,
            'current_price': self.last_price,
            'change': self.change,
            'change_percent': self.change_percent,
            'last_updated': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'previous_close': self.previous_close,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'volume': self.volume,
            'error': self.error
        }


@dataclass
class InstrumentPrice:
    """Simple price data for WebSocket updates"""
    instrument_token: int
    tradingsymbol: str
    last_price: float
    timestamp: datetime
    volume: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'instrument_token': self.instrument_token,
            'tradingsymbol': self.tradingsymbol,
            'last_price': self.last_price,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'volume': self.volume
        }


@dataclass
class QuoteData:
    """Complete quote data from exchange"""
    tradingsymbol: str
    exchange: str
    instrument_token: int
    last_price: float
    net_change: float
    ohlc: Dict[str, float]
    timestamp: datetime
    volume: Optional[int] = None
    
    def to_price_data(self, instrument_name: str) -> PriceData:
        """Convert to PriceData model"""
        previous_close = self.ohlc.get('close', 0)
        change_percent = (self.net_change / previous_close * 100) if previous_close > 0 else 0
        
        return PriceData(
            instrument=instrument_name,
            last_price=self.last_price,
            change=self.net_change,
            change_percent=change_percent,
            timestamp=self.timestamp,
            previous_close=previous_close,
            open=self.ohlc.get('open'),
            high=self.ohlc.get('high'),
            low=self.ohlc.get('low'),
            volume=self.volume
        )

