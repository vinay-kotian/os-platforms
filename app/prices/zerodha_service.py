"""
Zerodha KiteConnect integration service.
"""
from kiteconnect import KiteConnect
from typing import Optional, Dict, List
from app.database.models import Database
from datetime import datetime, timedelta
import threading


class ZerodhaService:
    """Service for Zerodha KiteConnect operations."""
    
    # Class-level cache for instruments (shared across all instances)
    _instruments_cache: Optional[List[Dict]] = None
    _cache_timestamp: Optional[datetime] = None
    _cache_lock = threading.Lock()
    _cache_ttl_hours = 24  # Cache instruments for 24 hours
    
    def __init__(self):
        self.db = Database()
        self.kite: Optional[KiteConnect] = None
        self._initialize_kite()
    
    def _initialize_kite(self):
        """Initialize KiteConnect with stored API keys."""
        keys = self.db.get_zerodha_keys()
        if keys:
            try:
                self.kite = KiteConnect(api_key=keys['api_key'])
                # Note: Access token needs to be set after login
            except Exception as e:
                print(f"Error initializing KiteConnect: {e}")
                self.kite = None
    
    def is_configured(self) -> bool:
        """Check if Zerodha API keys are configured."""
        return self.kite is not None and self.db.get_zerodha_keys() is not None
    
    def set_api_keys(self, api_key: str, api_secret: str) -> bool:
        """Set Zerodha API keys (admin only)."""
        try:
            self.db.set_zerodha_keys(api_key, api_secret)
            self._initialize_kite()
            return True
        except Exception as e:
            print(f"Error setting API keys: {e}")
            return False
    
    def get_login_url(self) -> Optional[str]:
        """
        Get Zerodha login URL for OAuth flow.
        
        Note: The redirect URL must be configured in Zerodha Developer Console
        to match: <your_domain>/prices/zerodha/callback
        """
        if not self.kite:
            return None
        try:
            return self.kite.login_url()
        except Exception as e:
            print(f"Error getting login URL: {e}")
            return None
    
    def generate_session(self, request_token: str) -> Optional[str]:
        """
        Generate access token from request token.
        
        Args:
            request_token: Request token from Zerodha callback
        
        Returns:
            Access token or None
        """
        keys = self.db.get_zerodha_keys()
        if not keys or not self.kite:
            return None
        
        try:
            data = self.kite.generate_session(request_token, api_secret=keys['api_secret'])
            return data.get('access_token')
        except Exception as e:
            print(f"Error generating session: {e}")
            return None
    
    def set_access_token(self, access_token: str):
        """Set access token for API calls."""
        if self.kite:
            self.kite.set_access_token(access_token)
    
    def is_authenticated(self, user_id: Optional[int] = None) -> bool:
        """Check if user has valid Zerodha session."""
        if not self.kite:
            return False
        
        if user_id:
            session_data = self.db.get_zerodha_session(user_id)
            if session_data and session_data.get('access_token'):
                return True
        return False
    
    def load_user_session(self, user_id: int) -> bool:
        """Load and set access token for a user."""
        if not self.kite:
            return False
        
        session_data = self.db.get_zerodha_session(user_id)
        if session_data and session_data.get('access_token'):
            try:
                self.kite.set_access_token(session_data['access_token'])
                return True
            except Exception as e:
                print(f"Error loading user session: {e}")
                return False
        return False
    
    def _get_cached_instruments(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get instruments from cache or fetch from API if cache is stale.
        
        Args:
            force_refresh: If True, force refresh from API even if cache is valid
        
        Returns:
            List of instruments
        """
        with ZerodhaService._cache_lock:
            now = datetime.utcnow()
            
            # Check if cache is valid
            if (not force_refresh and 
                ZerodhaService._instruments_cache is not None and 
                ZerodhaService._cache_timestamp is not None and
                (now - ZerodhaService._cache_timestamp) < timedelta(hours=ZerodhaService._cache_ttl_hours)):
                return ZerodhaService._instruments_cache
            
            # Cache is stale or doesn't exist, fetch from API
            if not self.kite:
                # Return empty list if kite is not initialized
                return []
            
            try:
                print("Fetching instruments from Zerodha API (cache refresh)...")
                instruments = self.kite.instruments()
                ZerodhaService._instruments_cache = instruments
                ZerodhaService._cache_timestamp = now
                print(f"Cached {len(instruments)} instruments")
                return instruments
            except Exception as e:
                print(f"Error fetching instruments: {e}")
                # Return stale cache if available, otherwise empty list
                if ZerodhaService._instruments_cache is not None:
                    print("Using stale cache due to API error")
                    return ZerodhaService._instruments_cache
                return []
    
    def find_instrument(self, exchange: str, symbol: str) -> Optional[Dict]:
        """
        Find a specific instrument by exchange and symbol using cached data.
        This is much faster than searching all instruments.
        
        Args:
            exchange: Exchange (NSE, BSE, etc.)
            symbol: Trading symbol
        
        Returns:
            Instrument dict or None if not found
        """
        if not self.kite:
            return None
        
        instruments = self._get_cached_instruments()
        if not instruments:
            return None
        
        # Search in cached instruments
        exchange_upper = exchange.upper()
        symbol_upper = symbol.upper()
        
        for inst in instruments:
            if (inst.get('exchange', '').upper() == exchange_upper and 
                inst.get('tradingsymbol', '').upper() == symbol_upper):
                return {
                    'instrument_token': inst.get('instrument_token'),
                    'exchange_token': inst.get('exchange_token'),
                    'tradingsymbol': inst.get('tradingsymbol'),
                    'name': inst.get('name'),
                    'exchange': inst.get('exchange'),
                    'instrument_type': inst.get('instrument_type'),
                    'segment': inst.get('segment'),
                    'strike': inst.get('strike'),
                    'lot_size': inst.get('lot_size')
                }
        
        return None
    
    def search_instruments(self, query: str, exchange: Optional[str] = None) -> List[Dict]:
        """
        Search for instruments by name or symbol using cached data.
        
        Args:
            query: Search query (stock name or symbol)
            exchange: Optional exchange filter (NSE, BSE, etc.)
        
        Returns:
            List of matching instruments
        """
        if not self.kite:
            return []
        
        try:
            # Get instruments from cache (much faster than API call)
            instruments = self._get_cached_instruments()
            
            if not instruments:
                return []
            
            # Filter by exchange if provided
            if exchange:
                exchange_upper = exchange.upper()
                instruments = [inst for inst in instruments if inst.get('exchange', '').upper() == exchange_upper]
            
            # Search by name or tradingsymbol (case-insensitive)
            query_lower = query.lower()
            results = []
            
            for inst in instruments:
                name = inst.get('name', '').lower()
                tradingsymbol = inst.get('tradingsymbol', '').lower()
                
                if query_lower in name or query_lower in tradingsymbol:
                    results.append({
                        'instrument_token': inst.get('instrument_token'),
                        'exchange_token': inst.get('exchange_token'),
                        'tradingsymbol': inst.get('tradingsymbol'),
                        'name': inst.get('name'),
                        'exchange': inst.get('exchange'),
                        'instrument_type': inst.get('instrument_type'),
                        'segment': inst.get('segment'),
                        'strike': inst.get('strike'),
                        'lot_size': inst.get('lot_size')
                    })
            
            # Limit results to 50
            return results[:50]
        except Exception as e:
            print(f"Error searching instruments: {e}")
            return []
    
    def get_quote(self, exchange: str, symbol: str) -> Optional[Dict]:
        """
        Get quote for a specific instrument.
        
        Args:
            exchange: Exchange (NSE, BSE, etc.)
            symbol: Trading symbol
        
        Returns:
            Quote data or None
        """
        if not self.kite:
            return None
        
        try:
            instrument = f"{exchange}:{symbol}"
            quotes = self.kite.quote([instrument])
            
            if instrument in quotes:
                quote_data = quotes[instrument]
                return {
                    'last_price': quote_data.get('last_price', 0),
                    'ohlc': quote_data.get('ohlc', {}),
                    'net_change': quote_data.get('net_change', 0),
                    'timestamp': quote_data.get('timestamp')
                }
            return None
        except Exception as e:
            print(f"Error getting quote: {e}")
            return None
    
    def get_quotes(self, instruments: List[str]) -> Dict[str, Dict]:
        """
        Get quotes for multiple instruments.
        
        Args:
            instruments: List of instrument strings in format "EXCHANGE:SYMBOL"
        
        Returns:
            Dictionary of quotes keyed by instrument string
        """
        if not self.kite or not instruments:
            return {}
        
        try:
            quotes = self.kite.quote(instruments)
            result = {}
            
            for instrument, quote_data in quotes.items():
                result[instrument] = {
                    'last_price': quote_data.get('last_price', 0),
                    'ohlc': quote_data.get('ohlc', {}),
                    'net_change': quote_data.get('net_change', 0),
                    'timestamp': quote_data.get('timestamp')
                }
            
            return result
        except Exception as e:
            print(f"Error getting quotes: {e}")
            return {}

