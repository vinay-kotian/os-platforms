"""
Trade Rule Engine (TRE) service for processing alerts and generating trade signals.
"""
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from app.database.models import Database
from app.history.history_service import HistoryService
from app.prices.zerodha_service import ZerodhaService
import logging

logger = logging.getLogger(__name__)


class TREService:
    """Service for Trade Rule Engine operations."""
    
    def __init__(self, user_id: Optional[int] = None):
        self.db = Database()
        self.history_service = HistoryService(user_id)
        self.zerodha = ZerodhaService()
        self.user_id = user_id
        
        # Load user session if authenticated
        if user_id:
            self.zerodha.load_user_session(user_id)
    
    def process_alert(self, alert_data: Dict) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Process a triggered alert and generate trade signal.
        
        Args:
            alert_data: Dictionary containing:
                - level_alert_id: ID of the triggered alert
                - user_id: User ID
                - exchange: Exchange (NSE, BSE, etc.)
                - symbol: Trading symbol
                - price_level: Alert price level
                - current_price: Current price that triggered the alert
                - triggered_at: Timestamp when alert was triggered
                - price_data: Current price data
        
        Returns:
            (success: bool, trade_signal_id: Optional[int], error_message: Optional[str])
        """
        try:
            user_id = alert_data.get('user_id')
            exchange = alert_data.get('exchange')
            symbol = alert_data.get('symbol')
            current_price = alert_data.get('current_price')
            level_alert_id = alert_data.get('level_alert_id')
            
            if not all([user_id, exchange, symbol, current_price]):
                return False, None, "Missing required alert data"
            
            # Get TRE settings for user
            tre_settings = self.db.get_tre_settings(user_id)
            if not tre_settings or not tre_settings.get('is_active'):
                return False, None, "TRE settings not configured or inactive"
            
            stop_loss_percent = tre_settings.get('stop_loss_percent', 2.0)
            target_percent = tre_settings.get('target_percent', 5.0)
            lookback_minutes = tre_settings.get('trend_lookback_minutes', 20)
            
            # Get alert details to get TTL type
            from app.alerts.alert_service import AlertService
            alert_service = AlertService(user_id)
            level_alert = alert_service.get_level_alert(level_alert_id, user_id)
            if not level_alert:
                return False, None, "Level alert not found"
            
            ttl_type = level_alert.get('ttl_type', 'intraday')
            
            # Determine if price came from above or below the level
            # Price coming from TOP (above) to level -> Buy CALL
            # Price coming from BOTTOM (below) to level -> Buy PUT
            price_direction = self._determine_price_direction(
                exchange=exchange,
                symbol=symbol,
                level_price=level_alert.get('price_level'),
                current_price=current_price,
                lookback_minutes=lookback_minutes
            )
            
            if not price_direction:
                return False, None, "Could not determine price direction"
            
            # Determine option type based on where price came from
            # If price came from TOP (above level) -> Buy CALL
            # If price came from BOTTOM (below level) -> Buy PUT
            option_type = 'CALL' if price_direction == 'from_top' else 'PUT'
            trend_direction = 'downtrend' if price_direction == 'from_top' else 'uptrend'
            
            # Calculate strike price (for ITM options, we'll use current price as strike)
            # In real implementation, you'd find the nearest ITM strike
            strike_price = current_price
            
            # Calculate entry price (current price)
            entry_price = current_price
            
            # Calculate stop loss and target
            if option_type == 'CALL':
                # For CALL: SL below entry, Target above entry
                stop_loss = entry_price * (1 - stop_loss_percent / 100)
                target = entry_price * (1 + target_percent / 100)
            else:  # PUT
                # For PUT: SL above entry, Target below entry
                stop_loss = entry_price * (1 + stop_loss_percent / 100)
                target = entry_price * (1 - target_percent / 100)
            
            # Get instrument token if available
            instrument = self.zerodha.find_instrument(exchange, symbol)
            instrument_token = instrument.get('instrument_token') if instrument else None
            
            # Check if similar trade signal already exists (prevent duplicates)
            existing_signals = self.db.get_trade_signals(user_id=user_id, status='pending')
            for signal in existing_signals:
                if (signal['exchange'] == exchange and 
                    signal['symbol'] == symbol and
                    signal['option_type'] == option_type and
                    abs(signal['entry_price'] - entry_price) < entry_price * 0.01):  # Within 1% of entry price
                    logger.info(f"Similar trade signal already exists: {signal['trade_signal_id']}")
                    return False, None, "Similar trade signal already pending"
            
            # Create trade signal
            trade_signal_id = self.db.create_trade_signal(
                user_id=user_id,
                level_alert_id=level_alert_id,
                exchange=exchange,
                symbol=symbol,
                instrument_token=instrument_token,
                option_type=option_type,
                strike_price=strike_price,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                trend_direction=trend_direction,
                ttl_type=ttl_type
            )
            
            if trade_signal_id:
                logger.info(f"Trade signal created: {trade_signal_id} for {exchange}:{symbol} - {option_type} (trend: {trend_direction})")
                return True, trade_signal_id, None
            else:
                return False, None, "Failed to create trade signal"
                
        except Exception as e:
            logger.error(f"Error processing alert in TRE: {e}", exc_info=True)
            return False, None, f"Error processing alert: {str(e)}"
    
    def _determine_price_direction(self, exchange: str, symbol: str, level_price: float,
                                   current_price: float, lookback_minutes: int = 20) -> Optional[str]:
        """
        Determine if price came from above (top) or below (bottom) the level price.
        
        Args:
            exchange: Exchange
            symbol: Trading symbol
            level_price: The alert level price
            current_price: Current price (should be at or near level_price)
            lookback_minutes: Number of minutes to look back
        
        Returns:
            'from_top' if price came from above the level, 'from_bottom' if from below, None if cannot determine
        """
        try:
            # Calculate date range for lookback
            to_date = datetime.now()
            from_date = to_date - timedelta(minutes=lookback_minutes)
            
            # Fetch historical data (minute candles)
            success, candles, error = self.history_service.get_historical_data(
                exchange=exchange,
                symbol=symbol,
                interval='minute',
                from_date=from_date.strftime('%Y-%m-%d %H:%M:%S'),
                to_date=to_date.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if not success or not candles or len(candles) < 2:
                logger.warning(f"Insufficient historical data to determine price direction for {exchange}:{symbol}")
                return None
            
            # Sort candles by timestamp (oldest first)
            candles_sorted = sorted(candles, key=lambda x: x['timestamp'])
            
            # Check prices at the start of the lookback period
            # We want to see if the price was above or below the level price
            start_price = candles_sorted[0]['close']
            
            # Also check average price over the lookback period
            avg_price = sum(c['close'] for c in candles_sorted) / len(candles_sorted)
            
            # Determine direction:
            # If start price was above level -> price came from TOP
            # If start price was below level -> price came from BOTTOM
            # Use a small tolerance (0.5%) to account for price fluctuations
            tolerance = level_price * 0.005
            
            if start_price > level_price + tolerance:
                # Price was above level, came from top
                logger.info(f"Price came from TOP: start={start_price}, level={level_price}, current={current_price}")
                return 'from_top'
            elif start_price < level_price - tolerance:
                # Price was below level, came from bottom
                logger.info(f"Price came from BOTTOM: start={start_price}, level={level_price}, current={current_price}")
                return 'from_bottom'
            else:
                # Price was near level, use average price to determine
                if avg_price > level_price + tolerance:
                    logger.info(f"Price came from TOP (using avg): avg={avg_price}, level={level_price}")
                    return 'from_top'
                elif avg_price < level_price - tolerance:
                    logger.info(f"Price came from BOTTOM (using avg): avg={avg_price}, level={level_price}")
                    return 'from_bottom'
                else:
                    # Price has been around the level, cannot determine
                    logger.warning(f"Cannot determine price direction: price has been around level {level_price}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error determining price direction: {e}", exc_info=True)
            return None
    
    def get_user_trade_signals(self, user_id: int, status: Optional[str] = None) -> List[Dict]:
        """Get trade signals for a user."""
        return self.db.get_trade_signals(user_id=user_id, status=status)
    
    def update_trade_signal_status(self, trade_signal_id: int, status: str) -> bool:
        """Update trade signal status."""
        return self.db.update_trade_signal_status(trade_signal_id, status)

