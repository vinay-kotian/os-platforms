"""
Price Publisher - Queue-based pub/sub system for publishing price updates to other modules.
"""
from queue import Queue, Empty
from threading import Thread, Lock
from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PricePublisher:
    """
    Lightweight queue-based publisher for price updates.
    Other modules can subscribe by registering a queue to receive price updates.
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one publisher instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PricePublisher, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the price publisher."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Dictionary to store subscriber queues: {subscriber_id: queue}
        self._subscribers: Dict[str, Queue] = {}
        self._subscriber_lock = Lock()
        
        # Background thread for distributing messages
        self._distributor_thread: Optional[Thread] = None
        self._running = False
        self._initialized = True
        
        logger.info("PricePublisher initialized")
    
    def start(self):
        """Start the background distributor thread."""
        if self._running:
            return
        
        self._running = True
        self._distributor_thread = Thread(target=self._distribute_messages, daemon=True)
        self._distributor_thread.start()
        logger.info("PricePublisher distributor thread started")
    
    def stop(self):
        """Stop the background distributor thread."""
        self._running = False
        if self._distributor_thread:
            self._distributor_thread.join(timeout=2)
        logger.info("PricePublisher distributor thread stopped")
    
    def subscribe(self, subscriber_id: str, queue: Optional[Queue] = None) -> Queue:
        """
        Subscribe to price updates.
        
        Args:
            subscriber_id: Unique identifier for the subscriber (e.g., 'alert_module', 'bre_module')
            queue: Optional queue to use. If None, a new queue will be created.
        
        Returns:
            The queue that will receive price updates
        
        Example:
            from app.prices.price_publisher import PricePublisher
            publisher = PricePublisher()
            publisher.start()
            my_queue = publisher.subscribe('alert_module')
            # In a background thread:
            while True:
                try:
                    price_update = my_queue.get(timeout=1)
                    # Process price update
                except Empty:
                    continue
        """
        with self._subscriber_lock:
            if queue is None:
                queue = Queue(maxsize=1000)  # Limit queue size to prevent memory issues
            
            self._subscribers[subscriber_id] = queue
            logger.info(f"Subscriber '{subscriber_id}' registered")
            
            # Start distributor if not already running
            if not self._running:
                self.start()
            
            return queue
    
    def unsubscribe(self, subscriber_id: str):
        """
        Unsubscribe from price updates.
        
        Args:
            subscriber_id: The subscriber ID to remove
        """
        with self._subscriber_lock:
            if subscriber_id in self._subscribers:
                del self._subscribers[subscriber_id]
                logger.info(f"Subscriber '{subscriber_id}' unregistered")
    
    def publish(self, instrument: str, price_data: Dict):
        """
        Publish a price update to all subscribers.
        
        Args:
            instrument: Instrument identifier in format "EXCHANGE:SYMBOL" (e.g., "NSE:TCS")
            price_data: Dictionary containing price information with keys:
                - exchange: Exchange name
                - symbol: Trading symbol
                - tradingsymbol: Trading symbol
                - name: Instrument name
                - last_price: Last traded price
                - previous_close: Previous close price
                - net_change: Net change in price
                - change_percent: Percentage change
                - ohlc: OHLC data dictionary
                - timestamp: Price timestamp
                - last_updated: Last update timestamp
        
        Example price_data:
            {
                'exchange': 'NSE',
                'symbol': 'TCS',
                'tradingsymbol': 'TCS',
                'name': 'TCS',
                'last_price': 3227.15,
                'previous_close': 3205.75,
                'net_change': 21.40,
                'change_percent': 0.67,
                'ohlc': {...},
                'timestamp': '2024-01-01T10:30:00',
                'last_updated': '2024-01-01T10:30:00'
            }
        """
        if not self._running:
            logger.warning("Publisher not started, cannot publish. Call start() first.")
            return
        
        # Create message with metadata
        message = {
            'instrument': instrument,
            'price_data': price_data,
            'published_at': datetime.utcnow().isoformat()
        }
        
        # Add to all subscriber queues
        with self._subscriber_lock:
            subscribers_to_remove = []
            
            for subscriber_id, queue in self._subscribers.items():
                try:
                    # Non-blocking put - if queue is full, log warning and skip
                    queue.put_nowait(message)
                except Exception as e:
                    logger.warning(f"Failed to publish to subscriber '{subscriber_id}': {e}")
                    # Mark for removal if queue operations fail
                    subscribers_to_remove.append(subscriber_id)
            
            # Remove failed subscribers
            for subscriber_id in subscribers_to_remove:
                del self._subscribers[subscriber_id]
                logger.warning(f"Removed subscriber '{subscriber_id}' due to queue errors")
    
    def _distribute_messages(self):
        """
        Background thread that distributes messages to subscribers.
        This is a placeholder for future enhancements if needed.
        Currently, messages are put directly into queues in publish().
        """
        while self._running:
            # For now, messages are distributed synchronously in publish()
            # This thread can be used for future enhancements like:
            # - Batching messages
            # - Retry logic
            # - Message filtering
            import time
            time.sleep(1)  # Just keep thread alive
    
    def get_subscriber_count(self) -> int:
        """Get the number of active subscribers."""
        with self._subscriber_lock:
            return len(self._subscribers)
    
    def get_subscriber_ids(self) -> List[str]:
        """Get list of all subscriber IDs."""
        with self._subscriber_lock:
            return list(self._subscribers.keys())


# Convenience function for other modules to easily subscribe
def get_price_publisher() -> PricePublisher:
    """
    Get the singleton PricePublisher instance.
    
    Returns:
        PricePublisher instance
    
    Example usage in other modules:
        from app.prices.price_publisher import get_price_publisher
        
        publisher = get_price_publisher()
        publisher.start()
        my_queue = publisher.subscribe('my_module')
    """
    return PricePublisher()

