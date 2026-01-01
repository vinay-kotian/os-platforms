# Price Publisher Usage Guide

The Price Publisher is a lightweight, queue-based pub/sub system that allows other modules to subscribe to real-time price updates.

## Overview

When prices are updated from Zerodha WebSocket, they are automatically published to all subscribed modules via Python queues. This is perfect for:
- Alert Management System - to check if prices breach alert thresholds
- Business Rule Engine (BRE) - to analyze price movements and trigger trades
- Order Orchestrator Platform - to monitor prices for stop-loss and target levels
- Ledger Platform - to track price changes for P&L calculations

## Basic Usage

### 1. Subscribe to Price Updates

```python
from app.prices.price_publisher import get_price_publisher
from queue import Empty
import threading

# Get the publisher instance
publisher = get_price_publisher()

# Subscribe with a unique subscriber ID
price_queue = publisher.subscribe('alert_module')  # or 'bre_module', 'order_module', etc.

# Process price updates in a background thread
def process_price_updates():
    while True:
        try:
            # Get price update (blocks for up to 1 second)
            message = price_queue.get(timeout=1)
            
            instrument = message['instrument']  # e.g., "NSE:TCS"
            price_data = message['price_data']
            published_at = message['published_at']
            
            # Extract price information
            exchange = price_data['exchange']
            symbol = price_data['symbol']
            last_price = price_data['last_price']
            previous_close = price_data['previous_close']
            net_change = price_data['net_change']
            change_percent = price_data['change_percent']
            
            # Your logic here
            print(f"Price update for {instrument}: {last_price} (Change: {change_percent}%)")
            
        except Empty:
            # Timeout - no message received, continue loop
            continue
        except Exception as e:
            print(f"Error processing price update: {e}")

# Start processing in a background thread
thread = threading.Thread(target=process_price_updates, daemon=True)
thread.start()
```

### 2. Price Data Structure

Each price update message contains:

```python
{
    'instrument': 'NSE:TCS',  # Format: "EXCHANGE:SYMBOL"
    'price_data': {
        'exchange': 'NSE',
        'symbol': 'TCS',
        'tradingsymbol': 'TCS',
        'name': 'TCS',
        'last_price': 3227.15,
        'previous_close': 3205.75,
        'net_change': 21.40,
        'change_percent': 0.67,
        'ohlc': {
            'open': 3210.00,
            'high': 3230.00,
            'low': 3205.00,
            'close': 3205.75
        },
        'timestamp': '2024-01-01T10:30:00',
        'last_updated': '2024-01-01T10:30:00'
    },
    'published_at': '2024-01-01T10:30:00.123456'  # When this message was published
}
```

### 3. Example: Alert Management Module

```python
from app.prices.price_publisher import get_price_publisher
from queue import Empty
import threading

class AlertManager:
    def __init__(self):
        self.publisher = get_price_publisher()
        self.price_queue = self.publisher.subscribe('alert_module')
        self.running = False
    
    def start(self):
        """Start monitoring prices for alerts."""
        self.running = True
        thread = threading.Thread(target=self._monitor_prices, daemon=True)
        thread.start()
    
    def _monitor_prices(self):
        """Monitor price updates and check alerts."""
        while self.running:
            try:
                message = self.price_queue.get(timeout=1)
                instrument = message['instrument']
                price_data = message['price_data']
                
                # Check if price breaches any alert thresholds
                self._check_alerts(instrument, price_data)
                
            except Empty:
                continue
            except Exception as e:
                print(f"Error in alert monitoring: {e}")
    
    def _check_alerts(self, instrument, price_data):
        """Check if price breaches alert thresholds."""
        last_price = price_data['last_price']
        # Your alert checking logic here
        # If alert triggered, send to BRE
        pass
```

### 4. Example: Business Rule Engine (BRE)

```python
from app.prices.price_publisher import get_price_publisher
from queue import Empty
import threading
from collections import deque

class BusinessRuleEngine:
    def __init__(self):
        self.publisher = get_price_publisher()
        self.price_queue = self.publisher.subscribe('bre_module')
        self.price_history = {}  # Store last 20 minutes of price data
        self.running = False
    
    def start(self):
        """Start the BRE."""
        self.running = True
        thread = threading.Thread(target=self._process_prices, daemon=True)
        thread.start()
    
    def _process_prices(self):
        """Process price updates and analyze for trade signals."""
        while self.running:
            try:
                message = self.price_queue.get(timeout=1)
                instrument = message['instrument']
                price_data = message['price_data']
                
                # Update price history
                self._update_price_history(instrument, price_data)
                
                # Analyze price movement in last 20 minutes
                if self._should_trigger_trade(instrument, price_data):
                    self._send_trade_to_order_orchestrator(instrument, price_data)
                
            except Empty:
                continue
            except Exception as e:
                print(f"Error in BRE: {e}")
    
    def _update_price_history(self, instrument, price_data):
        """Store price history for analysis."""
        if instrument not in self.price_history:
            self.price_history[instrument] = deque(maxlen=1200)  # ~20 minutes at 1 update/sec
        
        self.price_history[instrument].append({
            'price': price_data['last_price'],
            'timestamp': price_data['last_updated']
        })
    
    def _should_trigger_trade(self, instrument, price_data):
        """Check if trade should be triggered based on price velocity."""
        # Your BRE logic here
        return False
    
    def _send_trade_to_order_orchestrator(self, instrument, price_data):
        """Send trade signal to Order Orchestrator."""
        # Your logic here
        pass
```

## Advanced Usage

### Using Your Own Queue

If you want to use a custom queue with specific settings:

```python
from queue import Queue

# Create a custom queue with larger size
custom_queue = Queue(maxsize=5000)

# Subscribe with your custom queue
publisher = get_price_publisher()
publisher.subscribe('my_module', queue=custom_queue)
```

### Unsubscribing

```python
publisher = get_price_publisher()
publisher.unsubscribe('my_module')
```

### Checking Subscriber Status

```python
publisher = get_price_publisher()
subscriber_count = publisher.get_subscriber_count()
subscriber_ids = publisher.get_subscriber_ids()
print(f"Active subscribers: {subscriber_count}")
print(f"Subscriber IDs: {subscriber_ids}")
```

## Important Notes

1. **Thread Safety**: The publisher is thread-safe and can be used from multiple threads.

2. **Queue Size**: Default queue size is 1000 messages. If a queue is full, new messages will be dropped (with a warning logged). You can create a larger queue if needed.

3. **Daemon Threads**: Use daemon threads for background processing so they don't prevent the application from shutting down.

4. **Error Handling**: Always wrap queue operations in try-except blocks to handle potential errors gracefully.

5. **Performance**: The publisher uses in-memory queues, so it's very fast. However, if a subscriber is slow to process messages, the queue may fill up.

6. **Startup**: The publisher is automatically started when the Flask app initializes. You don't need to call `start()` manually unless you're using it outside the Flask app context.

## Integration with Flask App

The price publisher is automatically initialized and started when your Flask app starts. You can access it via:

```python
from flask import current_app

# In a Flask route or context
publisher = current_app.price_publisher
```

Or simply:

```python
from app.prices.price_publisher import get_price_publisher

publisher = get_price_publisher()  # Gets the singleton instance
```

## Best Practices

1. **Unique Subscriber IDs**: Use descriptive, unique subscriber IDs (e.g., 'alert_module', 'bre_module') to avoid conflicts.

2. **Background Processing**: Always process price updates in background threads to avoid blocking the main application.

3. **Error Recovery**: Implement retry logic and error recovery in your price processing code.

4. **Resource Cleanup**: Unsubscribe when your module shuts down to free resources.

5. **Monitoring**: Log important price events and monitor queue sizes to ensure your module is keeping up with price updates.

