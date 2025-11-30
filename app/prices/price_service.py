"""
Price service for managing price data and exchange connections
"""
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from .exchange_client import ExchangeClient
from .websocket_client import WebSocketClient
from .models import PriceData, QuoteData


class PriceService:
    """Service for price operations"""
    
    # Standard instrument tokens (fallback)
    NIFTY_50_TOKEN = 256265
    NIFTY_BANK_TOKEN = 260105
    
    def __init__(self, exchange_client: Optional[ExchangeClient] = None, 
                 websocket_client: Optional[WebSocketClient] = None):
        """
        Initialize price service
        
        Args:
            exchange_client: Exchange client instance (optional)
            websocket_client: WebSocket client instance (optional)
        """
        self.exchange_client = exchange_client or ExchangeClient()
        self.websocket_client = websocket_client or WebSocketClient()
        self._nifty_token: Optional[int] = None
        self._bank_nifty_token: Optional[int] = None
    
    def get_instrument_tokens(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Get instrument tokens for NIFTY 50 and NIFTY BANK
        
        Returns:
            Tuple of (nifty_token, bank_nifty_token)
        """
        if self._nifty_token and self._bank_nifty_token:
            return self._nifty_token, self._bank_nifty_token
        
        # Try to get from exchange
        if self.exchange_client.is_connected():
            self._nifty_token = self.exchange_client.get_instrument_token('NSE', 'NIFTY 50')
            self._bank_nifty_token = self.exchange_client.get_instrument_token('NSE', 'NIFTY BANK')
        
        # Fallback to standard tokens
        if not self._nifty_token:
            self._nifty_token = self.NIFTY_50_TOKEN
        if not self._bank_nifty_token:
            self._bank_nifty_token = self.NIFTY_BANK_TOKEN
        
        return self._nifty_token, self._bank_nifty_token
    
    def get_nifty_prices(self, use_websocket: bool = True) -> Dict[str, PriceData]:
        """
        Get prices for NIFTY 50 and NIFTY BANK
        
        Args:
            use_websocket: Whether to prefer WebSocket over REST API
        
        Returns:
            Dictionary with 'nifty' and 'bank_nifty' PriceData objects
        """
        result = {}
        
        # Try WebSocket first if available
        if use_websocket and self.websocket_client.is_running:
            nifty_token, bank_nifty_token = self.get_instrument_tokens()
            
            nifty_price = self.websocket_client.get_price(nifty_token)
            bank_nifty_price = self.websocket_client.get_price(bank_nifty_token)
            
            if nifty_price and nifty_price.get('last_price', 0) > 0:
                result['nifty'] = PriceData(
                    instrument='NIFTY 50',
                    last_price=nifty_price['last_price'],
                    change=0,  # WebSocket doesn't provide change
                    change_percent=0,
                    timestamp=datetime.fromisoformat(nifty_price.get('timestamp', datetime.now().isoformat()))
                        if isinstance(nifty_price.get('timestamp'), str)
                        else datetime.now()
                )
            
            if bank_nifty_price and bank_nifty_price.get('last_price', 0) > 0:
                result['bank_nifty'] = PriceData(
                    instrument='NIFTY BANK',
                    last_price=bank_nifty_price['last_price'],
                    change=0,
                    change_percent=0,
                    timestamp=datetime.fromisoformat(bank_nifty_price.get('timestamp', datetime.now().isoformat()))
                        if isinstance(bank_nifty_price.get('timestamp'), str)
                        else datetime.now()
                )
        
        # Fallback to REST API for complete data (including change/change_percent)
        if 'nifty' not in result or 'bank_nifty' not in result:
            quotes = self.exchange_client.get_quotes(['NSE:NIFTY 50', 'NSE:NIFTY BANK'])
            
            if 'NSE:NIFTY 50' in quotes:
                result['nifty'] = quotes['NSE:NIFTY 50'].to_price_data('NIFTY 50')
            
            if 'NSE:NIFTY BANK' in quotes:
                result['bank_nifty'] = quotes['NSE:NIFTY BANK'].to_price_data('NIFTY BANK')
        
        # If still no data, return error PriceData
        if 'nifty' not in result:
            result['nifty'] = PriceData(
                instrument='NIFTY 50',
                last_price=0,
                change=0,
                change_percent=0,
                timestamp=datetime.now(),
                error='Unable to fetch price. Please check your connection.'
            )
        
        if 'bank_nifty' not in result:
            result['bank_nifty'] = PriceData(
                instrument='NIFTY BANK',
                last_price=0,
                change=0,
                change_percent=0,
                timestamp=datetime.now(),
                error='Unable to fetch price. Please check your connection.'
            )
        
        return result
    
    def get_price(self, exchange: str, tradingsymbol: str) -> Optional[PriceData]:
        """
        Get price for a single instrument
        
        Args:
            exchange: Exchange name (e.g., 'NSE')
            tradingsymbol: Trading symbol (e.g., 'NIFTY 50')
        
        Returns:
            PriceData or None
        """
        quote = self.exchange_client.get_quote(exchange, tradingsymbol)
        if quote:
            return quote.to_price_data(tradingsymbol)
        return None
    
    def is_exchange_connected(self) -> bool:
        """Check if exchange is connected"""
        return self.exchange_client.is_connected()
    
    def is_websocket_running(self) -> bool:
        """Check if WebSocket is running"""
        return self.websocket_client.is_running
    
    def start_websocket(self, api_key: str, access_token: str, user_id: str) -> bool:
        """
        Start WebSocket connection
        
        Args:
            api_key: Zerodha API key
            access_token: Access token
            user_id: User ID
        
        Returns:
            True if started successfully
        """
        if not self.websocket_client.connect(api_key, access_token, user_id):
            return False
        
        # Get tokens and subscribe
        nifty_token, bank_nifty_token = self.get_instrument_tokens()
        if nifty_token and bank_nifty_token:
            self.websocket_client.subscribe([nifty_token, bank_nifty_token])
        
        self.websocket_client.start()
        return True
    
    def stop_websocket(self):
        """Stop WebSocket connection"""
        self.websocket_client.stop()

