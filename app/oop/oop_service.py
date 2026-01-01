"""
Order Orchestrator Platform (OOP) service for managing GTT orders and paper trades.
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from app.database.models import Database
from app.prices.price_publisher import get_price_publisher
from app.prices.zerodha_service import ZerodhaService
from queue import Queue, Empty
from threading import Thread
import logging

logger = logging.getLogger(__name__)


class OOPService:
    """Service for Order Orchestrator Platform operations."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(OOPService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize OOP service."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.db = Database()
        self.price_publisher = get_price_publisher()
        self.price_queue: Optional[Queue] = None
        self.monitor_thread: Optional[Thread] = None
        self.running = False
        self._initialized = True
        
        logger.info("OOPService initialized")
    
    def create_order_from_signal(self, trade_signal_id: int) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Create a GTT order with OCO from a trade signal.
        Supports both paper trading and actual trading.
        
        Args:
            trade_signal_id: ID of the trade signal from TRE
        
        Returns:
            (success: bool, order_id: Optional[int], error_message: Optional[str])
        """
        try:
            # Get trade signal
            signals = self.db.get_trade_signals(status='pending')
            signal = None
            for s in signals:
                if s['trade_signal_id'] == trade_signal_id:
                    signal = s
                    break
            
            if not signal:
                return False, None, "Trade signal not found or already processed"
            
            user_id = signal['user_id']
            exchange = signal['exchange']
            symbol = signal['symbol']
            option_type = signal['option_type']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            target = signal['target']
            ttl_type = signal['ttl_type']
            instrument_token = signal.get('instrument_token')
            
            # Check if user has paper trading enabled
            oop_settings = self.db.get_oop_settings(user_id)
            paper_trading = True  # Default to paper trading
            if oop_settings:
                paper_trading = bool(oop_settings.get('paper_trading', True))
            
            # Create GTT order in database
            order_id = self.db.create_oop_order(
                user_id=user_id,
                trade_signal_id=trade_signal_id,
                exchange=exchange,
                symbol=symbol,
                instrument_token=instrument_token,
                option_type=option_type,
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                target_price=target,
                quantity=1,
                ttl_type=ttl_type
            )
            
            if order_id:
                # Mark trade signal as sent
                from app.tre.tre_service import TREService
                tre_service = TREService(user_id)
                tre_service.update_trade_signal_status(trade_signal_id, 'sent')
                
                if paper_trading:
                    # Paper trading: just activate the order, monitor will handle execution
                    self.db.update_oop_order_status(order_id, 'active')
                    logger.info(f"Paper trade GTT order created: {order_id} for {exchange}:{symbol} - {option_type}")
                else:
                    # Actual trading: place real orders via Zerodha API
                    success, error = self._place_real_order(
                        user_id=user_id,
                        order_id=order_id,
                        exchange=exchange,
                        symbol=symbol,
                        instrument_token=instrument_token,
                        option_type=option_type,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        target=target,
                        quantity=1,
                        ttl_type=ttl_type
                    )
                    
                    if success:
                        self.db.update_oop_order_status(order_id, 'active')
                        logger.info(f"Real GTT order placed: {order_id} for {exchange}:{symbol} - {option_type}")
                    else:
                        # Mark order as failed
                        self.db.update_oop_order_status(order_id, 'cancelled')
                        return False, None, f"Failed to place real order: {error}"
                
                return True, order_id, None
            else:
                return False, None, "Failed to create order"
                
        except Exception as e:
            logger.error(f"Error creating order from signal: {e}", exc_info=True)
            return False, None, f"Error creating order: {str(e)}"
    
    def _place_real_order(self, user_id: int, order_id: int, exchange: str, symbol: str,
                         instrument_token: Optional[str], option_type: str,
                         entry_price: float, stop_loss: float, target: float,
                         quantity: int, ttl_type: str = 'intraday') -> Tuple[bool, Optional[str]]:
        """
        Place real orders via Zerodha Kite API.
        
        Args:
            user_id: User ID
            order_id: OOP order ID
            exchange: Exchange
            symbol: Symbol
            instrument_token: Instrument token
            option_type: CALL or PUT
            entry_price: Entry price
            stop_loss: Stop loss price
            target: Target price
            quantity: Quantity
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            zerodha = ZerodhaService()
            
            # Check if Zerodha is configured and user is authenticated
            if not zerodha.is_configured():
                return False, "Zerodha API keys not configured"
            
            if not zerodha.is_authenticated(user_id):
                return False, "Zerodha session not found. Please connect to Zerodha first."
            
            # Load user session
            if not zerodha.load_user_session(user_id):
                return False, "Failed to load Zerodha session"
            
            if not zerodha.kite:
                return False, "KiteConnect not initialized"
            
            # Get instrument details
            instrument = zerodha.find_instrument(exchange, symbol)
            if not instrument:
                return False, f"Instrument {exchange}:{symbol} not found"
            
            tradingsymbol = instrument.get('tradingsymbol', symbol)
            
            # Determine transaction type
            # For CALL: BUY, For PUT: BUY (we're buying options)
            transaction_type = "BUY"
            
            # Place entry order (MARKET order at entry price)
            # Note: For GTT, we'll use limit order at entry price
            # In real implementation, you might want to use GTT API if available
            try:
                entry_order = zerodha.kite.place_order(
                    variety="regular",
                    exchange=exchange,
                    tradingsymbol=tradingsymbol,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    order_type="LIMIT",
                    product="MIS" if ttl_type == 'intraday' else "NRML",
                    price=entry_price,
                    validity="DAY"
                )
                
                logger.info(f"Entry order placed: {entry_order} for order {order_id}")
                
                # Store Zerodha order ID in our database (we can add a field for this later)
                # For now, we'll monitor the order status
                
                return True, None
                
            except Exception as order_error:
                error_msg = str(order_error)
                logger.error(f"Error placing Zerodha order: {error_msg}")
                return False, f"Failed to place order: {error_msg}"
                
        except Exception as e:
            logger.error(f"Error placing real order: {e}", exc_info=True)
            return False, f"Error: {str(e)}"
    
    def start_monitoring(self):
        """Start monitoring prices for active orders."""
        if self.running:
            logger.warning("OOP monitor is already running")
            return
        
        # Subscribe to price updates
        self.price_queue = self.price_publisher.subscribe('oop_module')
        
        # Start monitoring thread
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_orders, daemon=True)
        self.monitor_thread.start()
        
        logger.info("OOP order monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring prices."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        # Unsubscribe from price updates
        if self.price_queue:
            self.price_publisher.unsubscribe('oop_module')
            self.price_queue = None
        
        logger.info("OOP order monitoring stopped")
    
    def _monitor_orders(self):
        """Background thread that monitors prices and executes orders."""
        while self.running:
            try:
                # Get price update (blocks for up to 1 second)
                message = self.price_queue.get(timeout=1)
                
                instrument = message['instrument']  # Format: "EXCHANGE:SYMBOL"
                price_data = message['price_data']
                
                # Check active orders for this instrument
                self._check_orders(instrument, price_data)
                
            except Empty:
                # Timeout - no message received, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in OOP order monitoring: {e}", exc_info=True)
    
    def _check_orders(self, instrument: str, price_data: Dict):
        """
        Check if any active orders should be executed.
        
        Args:
            instrument: Instrument identifier (e.g., "NSE:TCS")
            price_data: Price data dictionary
        """
        try:
            # Parse instrument
            parts = instrument.split(':')
            if len(parts) != 2:
                return
            
            exchange = parts[0]
            symbol = parts[1]
            current_price = price_data.get('last_price', 0)
            
            if current_price <= 0:
                return
            
            # Get all active orders for this instrument
            active_orders = self.db.get_active_oop_orders()
            
            instrument_orders = [
                order for order in active_orders
                if order['exchange'] == exchange and order['symbol'] == symbol
            ]
            
            # Check each order
            for order in instrument_orders:
                # Check if order has expired (for intraday orders)
                if order['ttl_type'] == 'intraday' and order.get('expires_at'):
                    expires_at = datetime.fromisoformat(order['expires_at'])
                    if datetime.utcnow() > expires_at:
                        # Order expired, close it
                        self._close_order(order['order_id'], current_price, 'time_based')
                        continue
                
                # Check if it's after 3:00 PM IST (9:30 AM UTC) - close intraday orders
                now = datetime.utcnow()
                if order['ttl_type'] == 'intraday' and now.hour >= 9 and now.minute >= 30:
                    self._close_order(order['order_id'], current_price, 'time_based')
                    continue
                
                entry_price = order['entry_price']
                stop_loss_price = order['stop_loss_price']
                target_price = order['target_price']
                option_type = order['option_type']
                
                # Check if entry price is reached (for pending orders)
                if order['status'] == 'pending':
                    # For GTT orders, we execute at entry price
                    if abs(current_price - entry_price) <= entry_price * 0.001:  # 0.1% tolerance
                        # Entry triggered, order is now active
                        self.db.update_oop_order_status(order['order_id'], 'active', executed_price=entry_price)
                        logger.info(f"Order {order['order_id']} entry triggered at {entry_price}")
                    continue
                
                # For active orders, check target and stop loss
                if order['status'] == 'active':
                    executed = False
                    exit_reason = None
                    
                    if option_type == 'CALL':
                        # For CALL: target is above, SL is below
                        if current_price >= target_price:
                            # Target hit
                            exit_reason = 'target_hit'
                            executed = True
                        elif current_price <= stop_loss_price:
                            # Stop loss hit
                            exit_reason = 'stop_loss'
                            executed = True
                    else:  # PUT
                        # For PUT: target is below, SL is above
                        if current_price <= target_price:
                            # Target hit
                            exit_reason = 'target_hit'
                            executed = True
                        elif current_price >= stop_loss_price:
                            # Stop loss hit
                            exit_reason = 'stop_loss'
                            executed = True
                    
                    if executed:
                        # Execute order and cancel OCO group
                        self._execute_order(order, current_price, exit_reason)
            
        except Exception as e:
            logger.error(f"Error checking orders for {instrument}: {e}", exc_info=True)
    
    def _execute_order(self, order: Dict, exit_price: float, exit_reason: str):
        """
        Execute an order and handle OCO cancellation.
        Supports both paper trading and actual trading.
        
        Args:
            order: Order dictionary
            exit_price: Price at which order is executed
            exit_reason: Reason for exit ('target_hit' or 'stop_loss')
        """
        try:
            order_id = order['order_id']
            oco_group_id = order['oco_group_id']
            user_id = order['user_id']
            
            # Check if this is actual trading
            oop_settings = self.db.get_oop_settings(user_id)
            paper_trading = True  # Default to paper trading
            if oop_settings:
                paper_trading = bool(oop_settings.get('paper_trading', True))
            
            # Calculate P&L
            entry_price = order['entry_price']
            quantity = order.get('quantity', 1)
            
            if order['option_type'] == 'CALL':
                pnl = (exit_price - entry_price) * quantity
            else:  # PUT
                pnl = (entry_price - exit_price) * quantity
            
            pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
            
            # For actual trading, place exit order via Zerodha API
            if not paper_trading:
                exit_success, exit_error = self._place_exit_order(
                    user_id=user_id,
                    order=order,
                    exit_price=exit_price,
                    exit_reason=exit_reason
                )
                if not exit_success:
                    logger.error(f"Failed to place exit order for {order_id}: {exit_error}")
                    # Continue with paper trade record even if real order fails
            
            # Update order status
            status = 'target_hit' if exit_reason == 'target_hit' else 'stopped_out'
            self.db.update_oop_order_status(
                order_id,
                status,
                executed_price=exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent
            )
            
            # Cancel other orders in OCO group
            cancelled = self.db.cancel_oco_orders(oco_group_id, exclude_order_id=order_id)
            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} orders in OCO group {oco_group_id}")
            
            # Create trade record
            self.db.create_oop_trade(
                order_id=order_id,
                user_id=user_id,
                exchange=order['exchange'],
                symbol=order['symbol'],
                option_type=order['option_type'],
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                exit_reason=exit_reason,
                pnl=pnl,
                pnl_percent=pnl_percent
            )
            
            logger.info(f"Order {order_id} executed ({'Paper' if paper_trading else 'Real'}): {exit_reason} at {exit_price}, P&L: {pnl:.2f} ({pnl_percent:.2f}%)")
            
        except Exception as e:
            logger.error(f"Error executing order: {e}", exc_info=True)
    
    def _place_exit_order(self, user_id: int, order: Dict, exit_price: float,
                         exit_reason: str) -> Tuple[bool, Optional[str]]:
        """
        Place exit order via Zerodha API for actual trading.
        
        Args:
            user_id: User ID
            order: Order dictionary
            exit_price: Exit price
            exit_reason: Exit reason
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            zerodha = ZerodhaService()
            
            if not zerodha.is_configured() or not zerodha.is_authenticated(user_id):
                return False, "Zerodha not configured or authenticated"
            
            if not zerodha.load_user_session(user_id) or not zerodha.kite:
                return False, "Failed to load Zerodha session"
            
            # Get instrument details
            instrument = zerodha.find_instrument(order['exchange'], order['symbol'])
            if not instrument:
                return False, f"Instrument {order['exchange']}:{order['symbol']} not found"
            
            tradingsymbol = instrument.get('tradingsymbol', order['symbol'])
            quantity = order.get('quantity', 1)
            
            # Place SELL order to exit
            try:
                exit_order = zerodha.kite.place_order(
                    variety="regular",
                    exchange=order['exchange'],
                    tradingsymbol=tradingsymbol,
                    transaction_type="SELL",
                    quantity=quantity,
                    order_type="LIMIT",
                    product="MIS" if order.get('ttl_type') == 'intraday' else "NRML",
                    price=exit_price,
                    validity="DAY"
                )
                
                logger.info(f"Exit order placed: {exit_order} for order {order['order_id']}")
                return True, None
                
            except Exception as order_error:
                error_msg = str(order_error)
                logger.error(f"Error placing exit order: {error_msg}")
                return False, f"Failed to place exit order: {error_msg}"
                
        except Exception as e:
            logger.error(f"Error placing exit order: {e}", exc_info=True)
            return False, f"Error: {str(e)}"
    
    def _close_order(self, order_id: int, current_price: float, reason: str):
        """Close an order (expired or time-based)."""
        try:
            orders = self.db.get_oop_orders()
            order = None
            for o in orders:
                if o['order_id'] == order_id:
                    order = o
                    break
            
            if not order or order['status'] not in ['pending', 'active']:
                return
            
            # Calculate P&L if order was active
            if order['status'] == 'active':
                entry_price = order['entry_price']
                quantity = order.get('quantity', 1)
                
                if order['option_type'] == 'CALL':
                    pnl = (current_price - entry_price) * quantity
                else:  # PUT
                    pnl = (entry_price - current_price) * quantity
                
                pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
                
                # Create trade record
                self.db.create_oop_trade(
                    order_id=order_id,
                    user_id=order['user_id'],
                    exchange=order['exchange'],
                    symbol=order['symbol'],
                    option_type=order['option_type'],
                    entry_price=entry_price,
                    exit_price=current_price,
                    quantity=quantity,
                    exit_reason=reason,
                    pnl=pnl,
                    pnl_percent=pnl_percent
                )
                
                self.db.update_oop_order_status(
                    order_id,
                    'expired',
                    executed_price=current_price,
                    pnl=pnl,
                    pnl_percent=pnl_percent
                )
            else:
                # Order was pending, just mark as expired
                self.db.update_oop_order_status(order_id, 'expired')
            
            logger.info(f"Order {order_id} closed: {reason}")
            
        except Exception as e:
            logger.error(f"Error closing order: {e}", exc_info=True)
    
    def get_user_orders(self, user_id: int, status: Optional[str] = None) -> List[Dict]:
        """Get orders for a user."""
        return self.db.get_oop_orders(user_id=user_id, status=status)
    
    def get_user_trades(self, user_id: int, limit: Optional[int] = None) -> List[Dict]:
        """Get trades for a user."""
        return self.db.get_oop_trades(user_id=user_id, limit=limit)


# Convenience function
def get_oop_service() -> OOPService:
    """Get the singleton OOPService instance."""
    return OOPService()

