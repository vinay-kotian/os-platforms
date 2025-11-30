# Price Module Documentation

## Overview

A complete modular price fetching system has been created for the OS Platforms Trading System. This module handles fetching stock prices from Zerodha exchange using both REST API and WebSocket connections.

## What Was Created

### 1. **Module Structure** (`app/prices/`)

```
app/prices/
├── __init__.py              # Module exports
├── models.py                # Price domain models
├── exchange_client.py       # Zerodha API client wrapper
├── websocket_client.py      # WebSocket connection management
├── price_service.py         # Business logic
├── routes.py                # Flask routes
└── README.md                # Module documentation
```

### 2. **Models** (`models.py`)

- **PriceData**: Complete price information with OHLC data
- **InstrumentPrice**: Simple price data for WebSocket
- **QuoteData**: Complete quote from exchange API

### 3. **Exchange Client** (`exchange_client.py`)

- Wraps Zerodha KiteConnect API
- Methods for getting quotes, instrument tokens
- Connection status checking
- Error handling

### 4. **WebSocket Client** (`websocket_client.py`)

- Real-time price streaming
- Subscription management
- Price caching
- Callback support

### 5. **Price Service** (`price_service.py`)

- Business logic for price operations
- Automatic fallback from WebSocket to REST API
- Instrument token management
- Price data formatting

### 6. **Routes** (`routes.py`)

- `GET /prices` - Prices page
- `GET /prices/api/fetch` - Fetch prices API
- `GET /prices/api/quote` - Get specific quote
- `GET /prices/api/status` - Service status

## Features

### ✅ REST API Integration
- Fetch prices via Zerodha KiteConnect
- Get quotes for any instrument
- OHLC data retrieval

### ✅ WebSocket Support
- Real-time price streaming
- Automatic subscription management
- Price caching

### ✅ Automatic Fallback
- WebSocket → REST API fallback
- Graceful error handling
- Connection status checking

### ✅ Modular Design
- Clean separation of concerns
- Reusable components
- Easy to test

## Integration

### With Main App

The price module is integrated into `app.py`:
```python
from app.prices.routes import prices_bp
app.register_blueprint(prices_bp)
```

### With Auth Module

All price routes use `@login_required` decorator from auth module.

### With Services Module

Price module accesses KiteConnect instance from services module for backward compatibility.

## Routes

### Web Routes
- `GET /prices` - Main prices page

### API Routes
- `GET /prices/api/fetch` - Fetch NIFTY 50 and NIFTY BANK prices
- `GET /prices/api/quote?exchange=NSE&symbol=NIFTY 50` - Get specific quote
- `GET /prices/api/status` - Check service status

### Legacy Routes (Redirects)
- `GET /stocks/fetch-price` → `/prices/api/fetch`
- `GET /stocks/fetch-price-websocket` → `/prices/api/fetch`

## Usage Examples

### Using Price Service

```python
from app.prices import PriceService

service = PriceService()

# Get NIFTY prices
prices = service.get_nifty_prices(use_websocket=True)
print(prices['nifty'].last_price)
print(prices['bank_nifty'].last_price)

# Get specific instrument
price = service.get_price('NSE', 'NIFTY 50')
```

### Using Exchange Client

```python
from app.prices import ExchangeClient

client = ExchangeClient()

# Check connection
if client.is_connected():
    quote = client.get_quote('NSE', 'NIFTY 50')
    print(quote.last_price)
```

### Using WebSocket Client

```python
from app.prices import WebSocketClient

ws = WebSocketClient()
ws.connect(api_key, access_token, user_id)
ws.subscribe([256265, 260105])  # NIFTY tokens
ws.start()

# Get cached price
price = ws.get_price(256265)
```

## API Examples

### Fetch Prices
```bash
curl http://localhost:5001/prices/api/fetch
```

Response:
```json
{
  "success": true,
  "prices": {
    "nifty": {
      "name": "NIFTY 50",
      "current_price": 19500.50,
      "change": 150.25,
      "change_percent": 0.78,
      "last_updated": "2025-11-29T21:00:00"
    },
    "bank_nifty": {
      "name": "NIFTY BANK",
      "current_price": 43500.75,
      "change": 200.50,
      "change_percent": 0.46,
      "last_updated": "2025-11-29T21:00:00"
    }
  }
}
```

### Get Quote
```bash
curl "http://localhost:5001/prices/api/quote?exchange=NSE&symbol=NIFTY%2050"
```

### Check Status
```bash
curl http://localhost:5001/prices/api/status
```

## Migration Notes

### Old Routes → New Routes

- `/prices` → `/prices` (same, but now uses module)
- `/stocks/fetch-price` → `/prices/api/fetch` (redirects)
- `/stocks/fetch-price-websocket` → `/prices/api/fetch` (redirects)

### Code Changes

Old code using `fetch_nifty_prices_websocket()` from services can continue to work, but new code should use `PriceService`.

## Benefits

1. **Modularity**: Price logic separated from main app
2. **Testability**: Each component can be tested independently
3. **Reusability**: Price service can be used by other modules
4. **Maintainability**: Clear structure and responsibilities
5. **Extensibility**: Easy to add new instruments or features

## Next Steps

1. Integrate WebSocket broadcasting with SocketIO
2. Add price history storage
3. Add more instruments support
4. Add price alerts functionality
5. Add caching layer for better performance

---

**Last Updated**: November 29, 2025
**Module Version**: 1.0

