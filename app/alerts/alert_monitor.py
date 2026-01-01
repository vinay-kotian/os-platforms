"""
Alert Monitor - Monitors price updates and triggers alerts when price levels are breached.
"""
from queue import Queue, Empty
from threading import Thread
from typing import Dict, Optional
from datetime import datetime
import logging
from app.prices.price_publisher import get_price_publisher
from app.alerts.alert_service import AlertService

logger = logging.getLogger(__name__)


class AlertMonitor:
    """
    Monitors price updates and checks if alerts are breached.
    When an alert is triggered, it sends a message to BRE (Business Rule Engine).
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(AlertMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the alert monitor."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.alert_service = AlertService()
        self.price_publisher = get_price_publisher()
        self.price_queue: Optional[Queue] = None
        self.monitor_thread: Optional[Thread] = None
        self.running = False
        self.bre_queue: Optional[Queue] = None  # Queue to send triggered alerts to BRE
        self._initialized = True
        
        logger.info("AlertMonitor initialized")
    
    def start(self, bre_queue: Optional[Queue] = None):
        """
        Start monitoring price updates.
        
        Args:
            bre_queue: Optional queue to send triggered alerts to BRE.
                      If None, alerts will just be logged.
        """
        if self.running:
            logger.warning("AlertMonitor is already running")
            return
        
        self.bre_queue = bre_queue
        
        # Subscribe to price updates
        self.price_queue = self.price_publisher.subscribe('alert_module')
        
        # Start monitoring thread
        self.running = True
        self.monitor_thread = Thread(target=self._monitor_prices, daemon=True)
        self.monitor_thread.start()
        
        logger.info("AlertMonitor started")
    
    def stop(self):
        """Stop monitoring price updates."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        
        # Unsubscribe from price updates
        if self.price_queue:
            self.price_publisher.unsubscribe('alert_module')
            self.price_queue = None
        
        logger.info("AlertMonitor stopped")
    
    def _monitor_prices(self):
        """Background thread that monitors price updates and checks alerts."""
        while self.running:
            try:
                # Get price update (blocks for up to 1 second)
                message = self.price_queue.get(timeout=1)
                
                instrument = message['instrument']  # Format: "EXCHANGE:SYMBOL"
                price_data = message['price_data']
                
                # Check if any alerts are breached for this instrument
                self._check_alerts(instrument, price_data)
                
            except Empty:
                # Timeout - no message received, continue loop
                continue
            except Exception as e:
                logger.error(f"Error in alert monitoring: {e}", exc_info=True)
    
    def _check_alerts(self, instrument: str, price_data: Dict):
        """
        Check if any alerts are breached for the given instrument.
        
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
            
            # Get all active level alerts for this instrument
            active_level_alerts = self.alert_service.get_active_level_alerts()
            
            # Filter level alerts for this specific instrument
            instrument_level_alerts = [
                level_alert for level_alert in active_level_alerts
                if level_alert['exchange'] == exchange and level_alert['symbol'] == symbol
            ]
            
            # Check each level alert
            for level_alert in instrument_level_alerts:
                # Check if level alert has expired (for intraday alerts)
                if level_alert['ttl_type'] == 'intraday' and level_alert.get('expires_at'):
                    expires_at = datetime.fromisoformat(level_alert['expires_at'])
                    if datetime.utcnow() > expires_at:
                        # Level alert expired, deactivate it
                        self.alert_service.update_level_alert(
                            level_alert['level_alert_id'],
                            level_alert['user_id'],
                            is_active=False
                        )
                        continue
                
                # Check if price level is reached (trigger when price equals or crosses the level)
                price_level = level_alert['price_level']
                # Use a small tolerance (0.01%) to account for floating point precision
                tolerance = price_level * 0.0001
                is_breached = abs(current_price - price_level) <= tolerance or current_price == price_level
                
                if is_breached:
                    # Check if it's after 3:00 PM IST (9:30 AM UTC) - no trading after 3:00 PM
                    now = datetime.utcnow()
                    if now.hour >= 9 and now.minute >= 30:
                        logger.info(f"Level alert {level_alert['level_alert_id']} breached but after 3:00 PM - not sending to BRE")
                        # Still mark as triggered but don't send to BRE
                        self.alert_service.mark_level_alert_triggered(level_alert['level_alert_id'])
                        continue
                    
                    # Trigger the level alert
                    logger.info(f"Level alert {level_alert['level_alert_id']} triggered: {instrument} at {current_price} (level: {price_level})")
                    
                    # Mark level alert as triggered
                    self.alert_service.mark_level_alert_triggered(level_alert['level_alert_id'])
                    
                    # Send to TRE (Trade Rule Engine)
                    self._send_to_tre(level_alert, price_data, current_price)
                    
                    # Send to BRE (Business Rule Engine) - keeping for backward compatibility
                    self._send_to_bre(level_alert, price_data, current_price)
        
        except Exception as e:
            logger.error(f"Error checking alerts for {instrument}: {e}", exc_info=True)
    
    def _send_to_bre(self, level_alert: Dict, price_data: Dict, current_price: float):
        """
        Send triggered level alert to Business Rule Engine (BRE).
        
        Args:
            level_alert: Level alert dictionary
            price_data: Current price data
            current_price: Current price that reached the level
        """
        try:
            bre_message = {
                'level_alert_id': level_alert['level_alert_id'],
                'user_id': level_alert['user_id'],
                'instrument': f"{level_alert['exchange']}:{level_alert['symbol']}",
                'exchange': level_alert['exchange'],
                'symbol': level_alert['symbol'],
                'price_level': level_alert['price_level'],
                'current_price': current_price,
                'triggered_at': datetime.utcnow().isoformat(),
                'price_data': price_data
            }
            
            if self.bre_queue:
                # Send to BRE queue
                try:
                    self.bre_queue.put_nowait(bre_message)
                    logger.info(f"Level alert {level_alert['level_alert_id']} sent to BRE")
                except Exception as e:
                    logger.error(f"Failed to send level alert to BRE: {e}")
            else:
                # No BRE queue, just log
                logger.info(f"Level alert triggered (no BRE queue): {bre_message}")
        
        except Exception as e:
            logger.error(f"Error sending level alert to BRE: {e}", exc_info=True)
    
    def _send_to_tre(self, level_alert: Dict, price_data: Dict, current_price: float):
        """
        Send triggered level alert to Trade Rule Engine (TRE).
        
        Args:
            level_alert: Level alert dictionary
            price_data: Current price data
            current_price: Current price that reached the level
        """
        try:
            tre_message = {
                'level_alert_id': level_alert['level_alert_id'],
                'user_id': level_alert['user_id'],
                'instrument': f"{level_alert['exchange']}:{level_alert['symbol']}",
                'exchange': level_alert['exchange'],
                'symbol': level_alert['symbol'],
                'price_level': level_alert['price_level'],
                'current_price': current_price,
                'triggered_at': datetime.utcnow().isoformat(),
                'price_data': price_data
            }
            
            # Send to TRE via direct service call (no Flask context needed)
            try:
                from app.tre.tre_service import TREService
                tre_service = TREService(level_alert['user_id'])
                success, trade_signal_id, error = tre_service.process_alert(tre_message)
                
                if success:
                    logger.info(f"Level alert {level_alert['level_alert_id']} processed by TRE, trade signal: {trade_signal_id}")
                else:
                    logger.warning(f"TRE failed to process alert {level_alert['level_alert_id']}: {error}")
            except Exception as service_error:
                logger.error(f"Failed to process alert in TRE: {service_error}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error sending level alert to TRE: {e}", exc_info=True)


# Convenience function
def get_alert_monitor() -> AlertMonitor:
    """Get the singleton AlertMonitor instance."""
    return AlertMonitor()

