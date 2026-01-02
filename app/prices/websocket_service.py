"""
WebSocket service for real-time price updates using Zerodha KiteTicker.
"""
from typing import Dict, List, Optional, Set
from threading import Lock
from kiteconnect import KiteTicker
from app.database.models import Database
from app.prices.zerodha_service import ZerodhaService
from app.prices.price_publisher import PricePublisher
from flask_socketio import SocketIO
import logging

logger = logging.getLogger(__name__)


class WebSocketService:
    """Service for managing Zerodha KiteTicker WebSocket connections."""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one WebSocket connection."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WebSocketService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize WebSocket service."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.db = Database()
        self.zerodha_service = ZerodhaService()
        self.kite_ticker: Optional[KiteTicker] = None
        self.socketio: Optional[SocketIO] = None
        self.subscribed_tokens: Set[int] = set()
        self.token_to_instrument: Dict[int, Dict] = {}
        self.token_previous_close: Dict[int, float] = {}  # Store previous close for each token
        self.is_connected = False
        self._lock = Lock()
        self.price_publisher = PricePublisher()
        self._initialized = True
    
    def set_socketio(self, socketio: SocketIO):
        """Set the Flask-SocketIO instance."""
        self.socketio = socketio
    
    def _get_user_access_token(self, user_id: int) -> Optional[str]:
        """Get access token for a user."""
        session_data = self.db.get_zerodha_session(user_id)
        if session_data and session_data.get('access_token'):
            return session_data['access_token']
        return None
    
    def _get_api_key(self) -> Optional[str]:
        """Get Zerodha API key."""
        keys = self.db.get_zerodha_keys()
        if keys:
            return keys.get('api_key')
        return None
    
    def _on_ticks(self, ws, ticks):
        """Handle incoming tick data from KiteTicker."""
        try:
            for tick in ticks:
                instrument_token = tick.get('instrument_token')
                if instrument_token not in self.token_to_instrument:
                    continue
                
                instrument_info = self.token_to_instrument[instrument_token]
                exchange = instrument_info.get('exchange')
                symbol = instrument_info.get('symbol')
                tradingsymbol = instrument_info.get('tradingsymbol', symbol)
                
                # Extract price data
                last_price = float(tick.get('last_price', 0) or 0)
                ohlc = tick.get('ohlc', {})
                
                # Get previous close from OHLC if available, otherwise use stored value
                previous_close = 0
                if ohlc and isinstance(ohlc, dict):
                    previous_close = float(ohlc.get('close', 0) or 0)
                
                # If OHLC close is not in this tick, use stored previous close
                if previous_close == 0:
                    previous_close = self.token_previous_close.get(instrument_token, 0)
                else:
                    # Store the previous close for future ticks
                    self.token_previous_close[instrument_token] = previous_close
                
                # If we still don't have previous close, try to get it from the tick's net_change
                # or calculate from last_price (though this won't be accurate)
                if previous_close == 0:
                    # Try to calculate from net_change if available
                    net_change_from_tick = tick.get('net_change')
                    if net_change_from_tick is not None and last_price > 0:
                        # If net_change is provided, we can work backwards
                        # But we need previous_close, so this is a fallback
                        # For now, skip percentage calculation if we don't have previous_close
                        previous_close = last_price  # This will make change_percent = 0
                    else:
                        previous_close = last_price  # Fallback, but change will be 0
                
                # Calculate net_change: current price - previous close
                # KiteTicker may or may not provide net_change directly
                net_change = tick.get('net_change')
                if net_change is None or net_change == 0:
                    # Calculate net_change if not provided
                    if previous_close > 0 and last_price > 0:
                        net_change = last_price - previous_close
                    else:
                        net_change = 0
                else:
                    net_change = float(net_change)
                
                # Calculate change percentage
                change_percent = 0
                if previous_close > 0 and previous_close != last_price:
                    change_percent = (net_change / previous_close) * 100
                
                price_data = {
                    'exchange': exchange,
                    'symbol': symbol,
                    'tradingsymbol': tradingsymbol,
                    'name': tradingsymbol,
                    'last_price': last_price,
                    'previous_close': previous_close,
                    'net_change': round(net_change, 2),
                    'change_percent': round(change_percent, 2),
                    'ohlc': ohlc,
                    'timestamp': tick.get('timestamp'),
                    'last_updated': tick.get('exchange_timestamp')
                }
                
                # Broadcast to all connected clients via SocketIO
                if self.socketio:
                    self.socketio.emit('price_update', {
                        'instrument': f"{exchange}:{symbol}",
                        'data': price_data
                    })
                
                # Publish to internal pub/sub system for other modules
                instrument_key = f"{exchange}:{symbol}"
                self.price_publisher.publish(instrument_key, price_data)
        except Exception as e:
            logger.error(f"Error processing tick data: {e}", exc_info=True)
    
    def _on_connect(self, ws, response):
        """Handle WebSocket connection."""
        logger.info(f"KiteTicker WebSocket connected. Response: {response}")
        self.is_connected = True
        if self.socketio:
            self.socketio.emit('websocket_status', {
                'connected': True,
                'message': 'Connected to Zerodha live prices'
            })
    
    def _on_close(self, ws, code, reason):
        """Handle WebSocket disconnection."""
        logger.info(f"KiteTicker WebSocket closed: {code} - {reason}")
        self.is_connected = False
        if self.socketio:
            self.socketio.emit('websocket_status', {
                'connected': False,
                'message': f'Disconnected from Zerodha: {reason or "Connection closed"}'
            })
    
    def _on_error(self, ws, code, reason):
        """Handle WebSocket errors."""
        error_msg = f"KiteTicker WebSocket error: {code} - {reason}"
        logger.error(error_msg)
        self.is_connected = False
        
        # Clean up on error
        if self.kite_ticker:
            try:
                self.kite_ticker = None
            except:
                pass
        
        if self.socketio:
            error_details = {
                'code': code,
                'reason': str(reason) if reason else 'Unknown error',
                'message': f'Zerodha websocket error: {reason or code}'
            }
            self.socketio.emit('websocket_error', error_details)
            self.socketio.emit('websocket_status', {
                'connected': False,
                'message': f'Connection error: {reason or code}'
            })
    
    def _on_reconnect(self, ws, attempts_count):
        """Handle WebSocket reconnection."""
        logger.info(f"KiteTicker WebSocket reconnecting (attempt {attempts_count})")
    
    def _on_noreconnect(self, ws):
        """Handle WebSocket reconnection failure."""
        logger.error("KiteTicker WebSocket failed to reconnect")
        self.is_connected = False
        if self.socketio:
            self.socketio.emit('websocket_status', {'connected': False})
    
    def connect(self, user_id: int) -> bool:
        """
        Connect to Zerodha KiteTicker WebSocket.
        
        Args:
            user_id: User ID to get access token for
        
        Returns:
            True if connection successful, False otherwise
        """
        with self._lock:
            if self.is_connected and self.kite_ticker:
                logger.info("KiteTicker already connected")
                return True
            
            api_key = self._get_api_key()
            access_token = self._get_user_access_token(user_id)
            
            if not api_key:
                logger.error("Zerodha API key not available")
                if self.socketio:
                    self.socketio.emit('websocket_error', {
                        'message': 'Zerodha API key not configured. Please contact administrator.'
                    })
                return False
            
            if not access_token:
                logger.error(f"Access token not available for user_id: {user_id}")
                if self.socketio:
                    self.socketio.emit('websocket_error', {
                        'message': 'Zerodha access token not found. Please connect to Zerodha first.'
                    })
                return False
            
            try:
                logger.info(f"Attempting to connect KiteTicker for user_id: {user_id}")
                
                # Create KiteTicker instance
                self.kite_ticker = KiteTicker(api_key, access_token)
                
                # Set callbacks
                self.kite_ticker.on_ticks = self._on_ticks
                self.kite_ticker.on_connect = self._on_connect
                self.kite_ticker.on_close = self._on_close
                self.kite_ticker.on_error = self._on_error
                self.kite_ticker.on_reconnect = self._on_reconnect
                self.kite_ticker.on_noreconnect = self._on_noreconnect
                
                # Connect in threaded mode
                self.kite_ticker.connect(threaded=True)
                
                # Wait for connection to establish (with timeout)
                import time
                max_wait = 5  # Maximum wait time in seconds
                wait_interval = 0.1  # Check every 100ms
                waited = 0
                
                while not self.is_connected and waited < max_wait:
                    time.sleep(wait_interval)
                    waited += wait_interval
                
                if self.is_connected:
                    logger.info("KiteTicker connection established successfully")
                    return True
                else:
                    logger.warning(f"KiteTicker connection timeout after {waited} seconds")
                    # Don't clean up immediately - the connection might still be establishing
                    # The error callback will handle cleanup if it fails
                    if self.socketio:
                        self.socketio.emit('websocket_error', {
                            'message': 'Connection to Zerodha websocket timed out. Please try again.'
                        })
                    return False
                    
            except Exception as e:
                logger.error(f"Error connecting to KiteTicker: {e}", exc_info=True)
                error_message = str(e)
                if self.socketio:
                    self.socketio.emit('websocket_error', {
                        'message': f'Failed to connect to Zerodha websocket: {error_message}'
                    })
                self.kite_ticker = None
                self.is_connected = False
                return False
    
    def disconnect(self):
        """Disconnect from Zerodha KiteTicker WebSocket."""
        with self._lock:
            if self.kite_ticker:
                try:
                    self.kite_ticker.close()
                except Exception as e:
                    logger.error(f"Error disconnecting KiteTicker: {e}")
                finally:
                    self.kite_ticker = None
                    self.is_connected = False
                    self.subscribed_tokens.clear()
                    self.token_to_instrument.clear()
    
    def subscribe_instruments(self, instruments: List[Dict], user_id: Optional[int] = None) -> bool:
        """
        Subscribe to instruments for real-time updates.
        
        Args:
            instruments: List of instrument dicts with exchange, symbol, instrument_token
            user_id: Optional user ID to load access token for quote fetching
        
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.kite_ticker or not self.is_connected:
            logger.warning("KiteTicker not connected, cannot subscribe")
            return False
        
        try:
            tokens_to_subscribe = []
            
            # First, try to get initial quotes to populate previous_close
            # This helps ensure we have previous_close for percentage calculations
            # Only if user_id is provided and access token can be loaded
            if user_id:
                try:
                    # Load user session to ensure access token is set
                    if self.zerodha_service.load_user_session(user_id):
                        kite = self.zerodha_service.kite
                        if kite:
                            instrument_strings = []
                            for inst in instruments:
                                exchange = inst.get('exchange')
                                symbol = inst.get('tradingsymbol') or inst.get('symbol')
                                if exchange and symbol:
                                    instrument_strings.append(f"{exchange}:{symbol}")
                            
                            if instrument_strings:
                                quotes = kite.quote(instrument_strings)
                                for inst_str, quote_data in quotes.items():
                                    ohlc = quote_data.get('ohlc', {})
                                    previous_close = ohlc.get('close', 0)
                                    if previous_close > 0:
                                        # Find the token for this instrument
                                        for inst in instruments:
                                            exchange = inst.get('exchange')
                                            symbol = inst.get('tradingsymbol') or inst.get('symbol')
                                            if f"{exchange}:{symbol}" == inst_str:
                                                token = int(inst.get('instrument_token', 0))
                                                if token > 0:
                                                    self.token_previous_close[token] = float(previous_close)
                                                    break
                    else:
                        logger.debug(f"Could not load user session for user_id: {user_id}, skipping initial quotes")
                except Exception as quote_error:
                    # Log as debug instead of warning since this is optional
                    logger.debug(f"Could not fetch initial quotes (optional): {quote_error}")
                    # Continue anyway - we'll try to get previous_close from tick data
            
            for inst in instruments:
                instrument_token = inst.get('instrument_token')
                if not instrument_token:
                    continue
                
                try:
                    token = int(instrument_token)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid instrument_token: {instrument_token}")
                    continue
                
                # Store mapping
                self.token_to_instrument[token] = {
                    'exchange': inst.get('exchange'),
                    'symbol': inst.get('symbol'),
                    'tradingsymbol': inst.get('tradingsymbol', inst.get('symbol'))
                }
                
                if token not in self.subscribed_tokens:
                    tokens_to_subscribe.append(token)
                    self.subscribed_tokens.add(token)
            
            if tokens_to_subscribe:
                # Subscribe to tokens
                self.kite_ticker.subscribe(tokens_to_subscribe)
                logger.info(f"Subscribed to {len(tokens_to_subscribe)} instruments")
            
            return True
        except Exception as e:
            logger.error(f"Error subscribing to instruments: {e}", exc_info=True)
            return False
    
    def unsubscribe_instruments(self, instrument_tokens: List[int]):
        """
        Unsubscribe from instruments.
        
        Args:
            instrument_tokens: List of instrument tokens to unsubscribe from
        """
        if not self.kite_ticker or not self.is_connected:
            return
        
        try:
            tokens_to_unsubscribe = []
            for token in instrument_tokens:
                if token in self.subscribed_tokens:
                    tokens_to_unsubscribe.append(token)
                    self.subscribed_tokens.discard(token)
                    self.token_to_instrument.pop(token, None)
            
            if tokens_to_unsubscribe:
                self.kite_ticker.unsubscribe(tokens_to_unsubscribe)
                logger.info(f"Unsubscribed from {len(tokens_to_unsubscribe)} instruments")
        except Exception as e:
            logger.error(f"Error unsubscribing from instruments: {e}")
    
    def get_subscribed_tokens(self) -> Set[int]:
        """Get set of currently subscribed instrument tokens."""
        return self.subscribed_tokens.copy()

