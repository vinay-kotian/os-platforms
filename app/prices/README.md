# Price Module

## Overview

The price module handles fetching and managing stock prices from the Zerodha exchange. It provides both REST API and WebSocket-based price fetching capabilities.

## Features

- ✅ REST API price fetching via Zerodha KiteConnect
- ✅ WebSocket real-time price streaming
- ✅ Automatic fallback from WebSocket to REST API
- ✅ Price data models with change/change_percent calculations
- ✅ Exchange connection management
- ✅ Instrument token management

## Module Structure

```
app/prices/
├── __init__.py              # Module exports
├── models.py                # Price data models (PriceData, InstrumentPrice, QuoteData)
├── exchange_client.py       # Zerodha API client wrapper
├── websocket_client.py      # WebSocket connection management
├── price_service.py         # Business logic for prices
├── routes.py                # Flask routes
└── README.md                # This file
```

## Usage

### Using Price Service

```python
from app.prices import PriceService

price_service = PriceService()

# Get NIFTY prices
prices = price_service.get_nifty_prices(use_websocket=True)
nifty_price = prices['nifty']
bank_nifty_price = prices['bank_nifty']

# Get specific instrument price
price = price_service.get_price('NSE', 'NIFTY 50')
```

### Using Exchange Client

```python
from app.prices import ExchangeClient

exchange = ExchangeClient()

# Get quote
quote = exchange.get_quote('NSE', 'NIFTY 50')

# Get multiple quotes
quotes = exchange.get_quotes(['NSE:NIFTY 50', 'NSE:NIFTY BANK'])

# Get instrument token
token = exchange.get_instrument_token('NSE', 'NIFTY 50')
```

### Using WebSocket Client

```python
from app.prices import WebSocketClient

ws_client = WebSocketClient()

# Connect
ws_client.connect(api_key, access_token, user_id)

# Subscribe to instruments
nifty_token, bank_nifty_token = 256265, 260105
ws_client.subscribe([nifty_token, bank_nifty_token])

# Start
ws_client.start()

# Get cached prices
price = ws_client.get_price(nifty_token)
```

## Routes

### Web Routes
- `GET /prices` - Prices page (displays NIFTY 50 and NIFTY BANK)

### API Routes
- `GET /prices/api/fetch` - Fetch current prices
- `GET /prices/api/quote?exchange=NSE&symbol=NIFTY 50` - Get quote for specific instrument
- `GET /prices/api/status` - Check price service status
- `GET /prices/api/fetch-websocket` - Legacy endpoint (redirects to /api/fetch)

## Models

### PriceData
Complete price information including:
- `instrument`: Instrument name
- `last_price`: Last traded price
- `change`: Price change
- `change_percent`: Percentage change
- `timestamp`: Last update time
- `previous_close`, `open`, `high`, `low`, `volume`: OHLC data

### InstrumentPrice
Simple price data for WebSocket:
- `instrument_token`: Token ID
- `tradingsymbol`: Trading symbol
- `last_price`: Last price
- `timestamp`: Update time

### QuoteData
Complete quote from exchange:
- All fields from exchange API
- Can convert to `PriceData` using `to_price_data()`

## Integration

The price module integrates with:
- **Auth Module**: Uses `@login_required` decorator
- **Services Module**: Accesses KiteConnect instance from services
- **WebSocket**: Broadcasts price updates via SocketIO

## Error Handling

- Automatic fallback from WebSocket to REST API
- Graceful error handling with error messages in PriceData
- Connection status checking before operations

## Example API Calls

### Fetch Prices
```bash
curl http://localhost:5001/prices/api/fetch
```

### Get Quote
```bash
curl "http://localhost:5001/prices/api/quote?exchange=NSE&symbol=NIFTY%2050"
```

### Check Status
```bash
curl http://localhost:5001/prices/api/status
```

## Notes

- WebSocket requires active connection to Zerodha
- REST API fallback is always available if WebSocket fails
- Instrument tokens are cached after first fetch
- Standard tokens (256265 for NIFTY 50, 260105 for NIFTY BANK) are used as fallback

