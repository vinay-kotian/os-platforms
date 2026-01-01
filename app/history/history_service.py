"""
History service for fetching historical candle data from Zerodha Kite API.
"""
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from app.prices.zerodha_service import ZerodhaService
from app.database.models import Database


class HistoryService:
    """Service for historical candle data operations."""
    
    # Valid intervals as per Kite API documentation
    VALID_INTERVALS = [
        'minute', '3minute', '5minute', '10minute', '15minute',
        '30minute', '60minute', 'day'
    ]
    
    def __init__(self, user_id: Optional[int] = None):
        self.db = Database()
        self.zerodha = ZerodhaService()
        self.user_id = user_id
        
        # Load user session if user is authenticated
        if user_id:
            self.zerodha.load_user_session(user_id)
    
    def get_historical_data(self, exchange: str, symbol: str, interval: str,
                           from_date: str, to_date: str,
                           continuous: bool = False, oi: bool = False) -> Tuple[bool, Optional[List], Optional[str]]:
        """
        Fetch historical candle data for an instrument.
        
        Args:
            exchange: Exchange (NSE, BSE, NFO, etc.)
            symbol: Trading symbol
            interval: Candle interval (minute, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute, day)
            from_date: Start date in 'yyyy-mm-dd hh:mm:ss' format
            to_date: End date in 'yyyy-mm-dd hh:mm:ss' format
            continuous: If True, get continuous data for futures/options
            oi: If True, include Open Interest data
        
        Returns:
            (success: bool, candles: Optional[List], error_message: Optional[str])
        """
        # Validate interval
        if interval not in self.VALID_INTERVALS:
            return False, None, f"Invalid interval. Must be one of: {', '.join(self.VALID_INTERVALS)}"
        
        # Check if Zerodha is configured
        if not self.zerodha.is_configured():
            return False, None, "Zerodha API keys not configured. Please contact administrator."
        
        # Check if user is authenticated
        if self.user_id and not self.zerodha.is_authenticated(self.user_id):
            return False, None, "Zerodha session not found. Please connect to Zerodha first."
        
        # Get instrument details to get instrument_token
        instrument = self.zerodha.find_instrument(exchange, symbol)
        if not instrument:
            return False, None, f"Instrument {exchange}:{symbol} not found"
        
        instrument_token = instrument.get('instrument_token')
        if not instrument_token:
            return False, None, f"Instrument token not found for {exchange}:{symbol}"
        
        # Ensure kite instance has access token
        if self.user_id:
            if not self.zerodha.load_user_session(self.user_id):
                return False, None, "Failed to load Zerodha session"
        
        if not self.zerodha.kite:
            return False, None, "KiteConnect not initialized"
        
        try:
            # Parse dates to ensure proper format
            try:
                from_dt = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S')
                to_dt = datetime.strptime(to_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return False, None, "Invalid date format. Use 'yyyy-mm-dd hh:mm:ss'"
            
            # Validate date range
            if from_dt >= to_dt:
                return False, None, "from_date must be before to_date"
            
            # Call Kite API to get historical data
            historical_data = self.zerodha.kite.historical_data(
                instrument_token=int(instrument_token),
                interval=interval,
                from_date=from_dt,
                to_date=to_dt,
                continuous=1 if continuous else 0,
                oi=1 if oi else 0
            )
            
            # Format the response
            # KiteConnect returns list of dictionaries with keys: date, open, high, low, close, volume, oi (if requested)
            candles = []
            for candle in historical_data:
                # Handle date - could be datetime or string
                timestamp = candle.get('date')
                if hasattr(timestamp, 'isoformat'):
                    timestamp_str = timestamp.isoformat()
                elif hasattr(timestamp, 'strftime'):
                    timestamp_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                candles.append({
                    'timestamp': timestamp_str,
                    'open': float(candle.get('open', 0)),
                    'high': float(candle.get('high', 0)),
                    'low': float(candle.get('low', 0)),
                    'close': float(candle.get('close', 0)),
                    'volume': int(candle.get('volume', 0)),
                    'oi': int(candle.get('oi', 0)) if oi and candle.get('oi') is not None else None
                })
            
            return True, candles, None
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error fetching historical data: {error_msg}")
            return False, None, f"Failed to fetch historical data: {error_msg}"
    
    def get_historical_data_simple(self, exchange: str, symbol: str, interval: str,
                                   days: int = 30) -> Tuple[bool, Optional[List], Optional[str]]:
        """
        Simplified method to fetch historical data for the last N days.
        
        Args:
            exchange: Exchange (NSE, BSE, NFO, etc.)
            symbol: Trading symbol
            interval: Candle interval
            days: Number of days to fetch (default: 30)
        
        Returns:
            (success: bool, candles: Optional[List], error_message: Optional[str])
        """
        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        # Format dates
        from_date_str = from_date.strftime('%Y-%m-%d %H:%M:%S')
        to_date_str = to_date.strftime('%Y-%m-%d %H:%M:%S')
        
        return self.get_historical_data(
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            from_date=from_date_str,
            to_date=to_date_str
        )

