"""
Exchange client for Zerodha API integration
"""
from datetime import datetime
from typing import Optional, Dict, List
from kiteconnect import KiteConnect
from flask import session, has_request_context
from .models import PriceData, QuoteData


class ExchangeClient:
    """Client for interacting with Zerodha exchange API"""
    
    def __init__(self, kite: Optional[KiteConnect] = None):
        """
        Initialize exchange client
        
        Args:
            kite: KiteConnect instance (optional, will be retrieved from services if not provided)
        """
        self.kite = kite
        if not self.kite:
            self._load_kite()
    
    def _load_kite(self):
        """Load KiteConnect instance from session or services module"""
        # First, try to get credentials from Flask session (most current)
        if has_request_context():
            try:
                api_key = session.get('api_key')
                access_token = session.get('access_token')
                
                if api_key and access_token:
                    # Initialize with current session credentials
                    self.kite = KiteConnect(api_key=api_key)
                    self.kite.set_access_token(access_token)
                    # Also update services.kite for consistency
                    try:
                        import services
                        services.kite = self.kite
                        services.user_api_key = api_key
                    except (ImportError, AttributeError):
                        pass
                    return
            except RuntimeError:
                # Not in request context, continue to fallback
                pass
        
        # Fallback to services.kite
        try:
            import services
            # If services.kite exists, use it
            if services.kite:
                self.kite = services.kite
            else:
                # Try to initialize from services credentials
                api_key = getattr(services, 'user_api_key', None)
                if api_key:
                    # Try to get access_token from file
                    import os
                    import json
                    session_file = getattr(services, 'SESSION_FILE', 'session_data.json')
                    if os.path.exists(session_file):
                        try:
                            with open(session_file, 'r') as f:
                                data = json.load(f)
                                access_token = data.get('access_token')
                                if access_token:
                                    self.kite = KiteConnect(api_key=api_key)
                                    self.kite.set_access_token(access_token)
                                    services.kite = self.kite
                                    return
                        except Exception:
                            pass
                self.kite = None
        except (ImportError, AttributeError):
            self.kite = None
    
    def _ensure_kite_initialized(self) -> bool:
        """Ensure kite is initialized with current credentials"""
        # If kite exists, assume it's valid (we'll catch errors in the actual API calls)
        # This avoids unnecessary profile() calls which can be rate-limited
        if self.kite:
            return True
        
        # Try to reload
        self._load_kite()
        return self.kite is not None
    
    def is_connected(self) -> bool:
        """Check if exchange is connected"""
        if not self._ensure_kite_initialized():
            return False
        try:
            # Try to get profile to verify connection
            self.kite.profile()
            return True
        except Exception:
            return False
    
    def get_quote(self, exchange: str, tradingsymbol: str) -> Optional[QuoteData]:
        """
        Get quote for an instrument
        
        Args:
            exchange: Exchange name (e.g., 'NSE')
            tradingsymbol: Trading symbol (e.g., 'NIFTY 50')
        
        Returns:
            QuoteData or None if error
        """
        if not self._ensure_kite_initialized():
            return None
        
        try:
            key = f"{exchange}:{tradingsymbol}"
            quote = self.kite.quote(key)
            instrument_data = quote.get(key, {})
            
            if not instrument_data:
                return None
            
            return QuoteData(
                tradingsymbol=instrument_data.get('tradingsymbol', tradingsymbol),
                exchange=exchange,
                instrument_token=instrument_data.get('instrument_token', 0),
                last_price=instrument_data.get('last_price', 0),
                net_change=instrument_data.get('net_change', 0),
                ohlc=instrument_data.get('ohlc', {}),
                timestamp=datetime.fromisoformat(instrument_data.get('timestamp', datetime.now().isoformat())) 
                    if isinstance(instrument_data.get('timestamp'), str) 
                    else datetime.now(),
                volume=instrument_data.get('volume', 0)
            )
        except Exception as e:
            error_msg = str(e)
            print(f"Error getting quote for {exchange}:{tradingsymbol}: {error_msg}")
            
            # Check if it's an authentication error
            if "api_key" in error_msg.lower() or "access_token" in error_msg.lower() or "invalid" in error_msg.lower() or "expired" in error_msg.lower():
                # Try to reinitialize with fresh credentials
                self.kite = None
                if self._ensure_kite_initialized():
                    # Retry once
                    try:
                        key = f"{exchange}:{tradingsymbol}"
                        quote = self.kite.quote(key)
                        instrument_data = quote.get(key, {})
                        if instrument_data:
                            return QuoteData(
                                tradingsymbol=instrument_data.get('tradingsymbol', tradingsymbol),
                                exchange=exchange,
                                instrument_token=instrument_data.get('instrument_token', 0),
                                last_price=instrument_data.get('last_price', 0),
                                net_change=instrument_data.get('net_change', 0),
                                ohlc=instrument_data.get('ohlc', {}),
                                timestamp=datetime.fromisoformat(instrument_data.get('timestamp', datetime.now().isoformat())) 
                                    if isinstance(instrument_data.get('timestamp'), str) 
                                    else datetime.now(),
                                volume=instrument_data.get('volume', 0)
                            )
                    except Exception as retry_error:
                        print(f"Retry failed for {exchange}:{tradingsymbol}: {retry_error}")
            
            return None
    
    def get_quotes(self, instruments: List[str]) -> Dict[str, QuoteData]:
        """
        Get quotes for multiple instruments
        
        Args:
            instruments: List of instrument keys (e.g., ['NSE:NIFTY 50', 'NSE:NIFTY BANK'])
        
        Returns:
            Dictionary mapping instrument keys to QuoteData
        """
        if not self._ensure_kite_initialized():
            return {}
        
        try:
            quotes = self.kite.quote(instruments)
            result = {}
            
            for key, instrument_data in quotes.items():
                if instrument_data:
                    result[key] = QuoteData(
                        tradingsymbol=instrument_data.get('tradingsymbol', ''),
                        exchange=key.split(':')[0],
                        instrument_token=instrument_data.get('instrument_token', 0),
                        last_price=instrument_data.get('last_price', 0),
                        net_change=instrument_data.get('net_change', 0),
                        ohlc=instrument_data.get('ohlc', {}),
                        timestamp=datetime.fromisoformat(instrument_data.get('timestamp', datetime.now().isoformat()))
                            if isinstance(instrument_data.get('timestamp'), str)
                            else datetime.now(),
                        volume=instrument_data.get('volume', 0)
                    )
            
            return result
        except Exception as e:
            print(f"Error getting quotes: {e}")
            return {}
    
    def get_instrument_token(self, exchange: str, tradingsymbol: str) -> Optional[int]:
        """
        Get instrument token for a symbol
        
        Args:
            exchange: Exchange name (e.g., 'NSE')
            tradingsymbol: Trading symbol (e.g., 'NIFTY 50')
        
        Returns:
            Instrument token or None
        """
        if not self._ensure_kite_initialized():
            return None
        
        try:
            instruments = self.kite.instruments(exchange)
            for instrument in instruments:
                if instrument['tradingsymbol'] == tradingsymbol:
                    return instrument['instrument_token']
            return None
        except Exception as e:
            print(f"Error getting instrument token: {e}")
            return None
    
    def get_instrument_tokens(self, instruments: List[tuple]) -> Dict[str, int]:
        """
        Get instrument tokens for multiple symbols
        
        Args:
            instruments: List of (exchange, tradingsymbol) tuples
        
        Returns:
            Dictionary mapping tradingsymbol to instrument_token
        """
        if not self._ensure_kite_initialized():
            return {}
        
        result = {}
        try:
            for exchange, tradingsymbol in instruments:
                token = self.get_instrument_token(exchange, tradingsymbol)
                if token:
                    result[tradingsymbol] = token
        except Exception as e:
            print(f"Error getting instrument tokens: {e}")
        
        return result
    
    def search_instruments(self, query: str, exchange: str = 'NSE', limit: int = 20) -> List[Dict]:
        """
        Search for instruments by symbol or name
        
        Args:
            query: Search query (symbol or name)
            exchange: Exchange name (default: 'NSE')
            limit: Maximum number of results (default: 20)
        
        Returns:
            List of instrument dictionaries with tradingsymbol, name, exchange, instrument_type
        """
        if not self._ensure_kite_initialized():
            return []
        
        if not query or len(query) < 2:
            return []
        
        try:
            # Get all instruments for the exchange
            instruments = self.kite.instruments(exchange)
            
            # Normalize query for case-insensitive search
            query_upper = query.upper().strip()
            
            # Filter instruments that match the query
            results = []
            for instrument in instruments:
                tradingsymbol = instrument.get('tradingsymbol', '').upper()
                name = instrument.get('name', '').upper()
                
                # Match if query is in tradingsymbol or name
                if query_upper in tradingsymbol or query_upper in name:
                    results.append({
                        'tradingsymbol': instrument.get('tradingsymbol'),
                        'name': instrument.get('name'),
                        'exchange': instrument.get('exchange', exchange),
                        'instrument_type': instrument.get('instrument_type', 'EQ'),
                        'segment': instrument.get('segment', '')
                    })
                    
                    # Stop if we've reached the limit
                    if len(results) >= limit:
                        break
            
            # Sort by relevance (exact matches first, then prefix matches)
            results.sort(key=lambda x: (
                0 if x['tradingsymbol'].upper().startswith(query_upper) else 1,
                x['tradingsymbol']
            ))
            
            return results
        except Exception as e:
            print(f"Error searching instruments: {e}")
            return []

