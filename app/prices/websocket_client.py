"""
WebSocket client for real-time price updates
"""
from datetime import datetime
from typing import Optional, Dict, Callable
from collections import deque
from kiteconnect import KiteTicker


class WebSocketClient:
    """WebSocket client for real-time price streaming"""
    
    def __init__(self):
        """Initialize WebSocket client"""
        self.kws: Optional[KiteTicker] = None
        self.is_running = False
        self.price_cache: Dict[str, Dict] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.subscribed_tokens: set = set()
    
    def connect(self, api_key: str, access_token: str, user_id: str) -> bool:
        """
        Connect to WebSocket
        
        Args:
            api_key: Zerodha API key
            access_token: Access token
            user_id: User ID
        
        Returns:
            True if connected successfully
        """
        try:
            self.kws = KiteTicker(api_key, access_token, user_id)
            self._setup_callbacks()
            return True
        except Exception as e:
            print(f"Error connecting WebSocket: {e}")
            return False
    
    def _setup_callbacks(self):
        """Setup WebSocket callbacks"""
        if not self.kws:
            return
        
        def on_ticks(ws, ticks):
            """Handle incoming ticks"""
            try:
                for tick in ticks:
                    instrument_token = tick['instrument_token']
                    last_price = tick.get('last_price', 0)
                    timestamp = datetime.now()
                    
                    # Update cache
                    token_str = str(instrument_token)
                    self.price_cache[token_str] = {
                        'last_price': last_price,
                        'timestamp': timestamp.isoformat(),
                        'volume': tick.get('volume', 0)
                    }
                    
                    # Call registered callbacks
                    if token_str in self.callbacks:
                        self.callbacks[token_str](tick)
            except Exception as e:
                print(f"Error processing WebSocket ticks: {e}")
        
        def on_connect(ws, response):
            """Handle WebSocket connection"""
            print("WebSocket connected")
            self.is_running = True
        
        def on_close(ws, code, reason):
            """Handle WebSocket close"""
            print(f"WebSocket closed: {code} - {reason}")
            self.is_running = False
        
        def on_error(ws, code, reason):
            """Handle WebSocket error"""
            print(f"WebSocket error: {code} - {reason}")
            self.is_running = False
        
        self.kws.on_ticks = on_ticks
        self.kws.on_connect = on_connect
        self.kws.on_close = on_close
        self.kws.on_error = on_error
    
    def subscribe(self, instrument_tokens: list, callback: Optional[Callable] = None):
        """
        Subscribe to instrument tokens
        
        Args:
            instrument_tokens: List of instrument tokens
            callback: Optional callback function for price updates
        """
        if not self.kws or not self.is_running:
            return
        
        try:
            # Register callbacks for tokens
            for token in instrument_tokens:
                token_str = str(token)
                self.subscribed_tokens.add(token)
                if callback:
                    self.callbacks[token_str] = callback
            
            # Subscribe to tokens
            self.kws.subscribe(instrument_tokens)
            self.kws.set_mode(self.kws.MODE_LTP, instrument_tokens)
        except Exception as e:
            print(f"Error subscribing to tokens: {e}")
    
    def unsubscribe(self, instrument_tokens: list):
        """Unsubscribe from instrument tokens"""
        if not self.kws or not self.is_running:
            return
        
        try:
            for token in instrument_tokens:
                token_str = str(token)
                self.subscribed_tokens.discard(token)
                self.callbacks.pop(token_str, None)
            
            self.kws.unsubscribe(instrument_tokens)
        except Exception as e:
            print(f"Error unsubscribing from tokens: {e}")
    
    def start(self):
        """Start WebSocket connection"""
        if not self.kws:
            return
        
        try:
            self.kws.connect(threaded=True)
        except Exception as e:
            print(f"Error starting WebSocket: {e}")
    
    def stop(self):
        """Stop WebSocket connection"""
        if self.kws:
            try:
                self.kws.close()
            except Exception:
                pass
        self.is_running = False
        self.price_cache.clear()
        self.callbacks.clear()
        self.subscribed_tokens.clear()
    
    def get_price(self, instrument_token: int) -> Optional[Dict]:
        """
        Get cached price for an instrument
        
        Args:
            instrument_token: Instrument token
        
        Returns:
            Price data dict or None
        """
        return self.price_cache.get(str(instrument_token))
    
    def get_prices(self, instrument_tokens: list) -> Dict[int, Dict]:
        """
        Get cached prices for multiple instruments
        
        Args:
            instrument_tokens: List of instrument tokens
        
        Returns:
            Dictionary mapping tokens to price data
        """
        result = {}
        for token in instrument_tokens:
            price_data = self.get_price(token)
            if price_data:
                result[token] = price_data
        return result

