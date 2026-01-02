"""
Price service for managing subscriptions and fetching live prices.
"""
from typing import Dict, List, Optional, Tuple
from app.database.models import Database
from app.prices.zerodha_service import ZerodhaService
from app.prices.websocket_service import WebSocketService
from datetime import datetime


class PriceService:
    """Service for price operations."""
    
    def __init__(self, user_id: Optional[int] = None):
        self.db = Database()
        self.zerodha = ZerodhaService()
        self.websocket_service = WebSocketService()
        self.user_id = user_id
        
        # Load user session if user is authenticated
        if user_id:
            self.zerodha.load_user_session(user_id)
    
    def subscribe(self, user_id: int, exchange: str, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Subscribe to an instrument.
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        if not self.zerodha.is_configured():
            return False, "Zerodha API keys not configured. Please contact administrator."
        
        # Use fast lookup instead of full search
        instrument = self.zerodha.find_instrument(exchange, symbol)
        
        if not instrument:
            return False, f"Instrument {exchange}:{symbol} not found"
        
        instrument_token = str(instrument.get('instrument_token', ''))
        tradingsymbol = instrument.get('tradingsymbol', symbol)
        
        subscription_id = self.db.add_subscription(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            instrument_token=instrument_token,
            tradingsymbol=tradingsymbol
        )
        
        if subscription_id:
            # Subscribe to websocket for real-time updates
            self._update_websocket_subscriptions(user_id)
            return True, None
        else:
            return False, "Already subscribed to this instrument"
    
    def _update_websocket_subscriptions(self, user_id: int):
        """Update websocket subscriptions for a user."""
        try:
            # Ensure websocket is connected
            if not self.websocket_service.is_connected:
                if not self.websocket_service.connect(user_id):
                    return  # Failed to connect
            
            # Get all subscriptions for the user
            subscriptions = self.get_user_subscriptions(user_id)
            
            # Prepare instruments for websocket subscription
            instruments = []
            for sub in subscriptions:
                if sub.get('instrument_token'):
                    instruments.append({
                        'instrument_token': sub['instrument_token'],
                        'exchange': sub['exchange'],
                        'symbol': sub['symbol'],
                        'tradingsymbol': sub.get('tradingsymbol', sub['symbol'])
                    })
            
            # Subscribe to websocket
            if instruments:
                self.websocket_service.subscribe_instruments(instruments, user_id)
        except Exception as e:
            print(f"Error updating websocket subscriptions: {e}")
    
    def unsubscribe(self, user_id: int, exchange: str, symbol: str) -> bool:
        """Unsubscribe from an instrument."""
        # Get subscription to find instrument_token before removing
        subscriptions = self.get_user_subscriptions(user_id)
        subscription = next(
            (s for s in subscriptions if s['exchange'] == exchange and s['symbol'] == symbol),
            None
        )
        
        success = self.db.remove_subscription(user_id, exchange, symbol)
        
        if success and subscription and subscription.get('instrument_token'):
            # Unsubscribe from websocket
            try:
                instrument_token = int(subscription['instrument_token'])
                self.websocket_service.unsubscribe_instruments([instrument_token])
            except (ValueError, TypeError):
                pass
        
        return success
    
    def get_user_subscriptions(self, user_id: int) -> List[Dict]:
        """Get all subscriptions for a user."""
        return self.db.get_user_subscriptions(user_id)
    
    def get_subscription_prices(self, user_id: int) -> Dict[str, Dict]:
        """
        Get current prices for all user subscriptions.
        
        Returns:
            Dictionary keyed by "EXCHANGE:SYMBOL" with price data
        """
        subscriptions = self.get_user_subscriptions(user_id)
        
        if not subscriptions:
            return {}
        
        # Build instrument list
        instruments = []
        subscription_map = {}
        
        for sub in subscriptions:
            exchange = sub['exchange']
            symbol = sub.get('tradingsymbol') or sub['symbol']
            instrument = f"{exchange}:{symbol}"
            instruments.append(instrument)
            subscription_map[instrument] = sub
        
        # Fetch quotes
        quotes = self.zerodha.get_quotes(instruments)
        
        # Format results with subscription info
        result = {}
        for instrument, quote_data in quotes.items():
            sub = subscription_map.get(instrument, {})
            ohlc = quote_data.get('ohlc', {})
            last_price = quote_data.get('last_price', 0)
            previous_close = ohlc.get('close', last_price)
            net_change = quote_data.get('net_change', 0)
            
            # Calculate change percentage
            change_percent = 0
            if previous_close > 0:
                change_percent = (net_change / previous_close) * 100
            
            result[instrument] = {
                'exchange': sub.get('exchange'),
                'symbol': sub.get('symbol'),
                'tradingsymbol': sub.get('tradingsymbol'),
                'name': sub.get('tradingsymbol', sub.get('symbol')),
                'last_price': last_price,
                'previous_close': previous_close,
                'net_change': net_change,
                'change_percent': round(change_percent, 2),
                'ohlc': ohlc,
                'timestamp': quote_data.get('timestamp'),
                'last_updated': datetime.utcnow().isoformat()
            }
        
        return result
    
    def get_all_subscription_prices(self) -> Dict[str, Dict]:
        """Get prices for all subscriptions across all users."""
        all_subscriptions = self.db.get_all_subscriptions()
        
        if not all_subscriptions:
            return {}
        
        # Group by unique instruments
        unique_instruments = {}
        for sub in all_subscriptions:
            exchange = sub['exchange']
            symbol = sub.get('tradingsymbol') or sub['symbol']
            instrument = f"{exchange}:{symbol}"
            if instrument not in unique_instruments:
                unique_instruments[instrument] = sub
        
        # Build instrument list
        instruments = list(unique_instruments.keys())
        
        # Fetch quotes
        quotes = self.zerodha.get_quotes(instruments)
        
        # Format results
        result = {}
        for instrument, quote_data in quotes.items():
            sub = unique_instruments.get(instrument, {})
            ohlc = quote_data.get('ohlc', {})
            last_price = quote_data.get('last_price', 0)
            previous_close = ohlc.get('close', last_price)
            net_change = quote_data.get('net_change', 0)
            
            # Calculate change percentage
            change_percent = 0
            if previous_close > 0:
                change_percent = (net_change / previous_close) * 100
            
            result[instrument] = {
                'exchange': sub.get('exchange'),
                'symbol': sub.get('symbol'),
                'tradingsymbol': sub.get('tradingsymbol'),
                'name': sub.get('tradingsymbol', sub.get('symbol')),
                'last_price': last_price,
                'previous_close': previous_close,
                'net_change': net_change,
                'change_percent': round(change_percent, 2),
                'ohlc': ohlc,
                'timestamp': quote_data.get('timestamp'),
                'last_updated': datetime.utcnow().isoformat()
            }
        
        return result

