# Curl Commands for Flask App

## Base URL
```
http://localhost:5001
```

## Available Endpoints

### 1. Home Page
```bash
curl -X GET http://localhost:5001/
```

### 2. Stock Prices Page
```bash
curl -X GET http://localhost:5001/prices
```

### 3. Fetch Stock Prices (API)
```bash
curl -X GET http://localhost:5001/stocks/fetch-price
```

### 4. Fetch Stock Prices via WebSocket (API)
```bash
curl -X GET http://localhost:5001/stocks/fetch-price-websocket
```

## Complete curl commands with headers

### Home Page (with headers)
```bash
curl -X GET \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: en-US,en;q=0.5" \
  -H "Accept-Encoding: gzip, deflate" \
  -H "Connection: keep-alive" \
  http://localhost:5001/
```

### Stock Prices Page (with headers)
```bash
curl -X GET \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: en-US,en;q=0.5" \
  -H "Accept-Encoding: gzip, deflate" \
  -H "Connection: keep-alive" \
  http://localhost:5001/prices
```

### Fetch Stock Prices API (with headers)
```bash
curl -X GET \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "Connection: keep-alive" \
  http://localhost:5001/stocks/fetch-price
```

### Fetch Stock Prices via WebSocket API (with headers)
```bash
curl -X GET \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -H "Connection: keep-alive" \
  http://localhost:5001/stocks/fetch-price-websocket
```

## Testing with verbose output
```bash
curl -v http://localhost:5001/
curl -v http://localhost:5001/prices
curl -v http://localhost:5001/stocks/fetch-price
curl -v http://localhost:5001/stocks/fetch-price-websocket
```

## Save responses to files
```bash
curl -X GET http://localhost:5001/ -o home_page.html
curl -X GET http://localhost:5001/prices -o prices_page.html
curl -X GET http://localhost:5001/stocks/fetch-price -o stock_data.json
curl -X GET http://localhost:5001/stocks/fetch-price-websocket -o websocket_prices.json
```

## Authentication

**✅ Automatic Authentication:** The API endpoints automatically use credentials from the stored session file (`session_data.json`). You only need to login once via the browser, and then all curl requests will work without needing to pass tokens or cookies.

**First-time setup:**
1. **Login via browser (one time only):**
   - Go to `http://localhost:5001/login`
   - Enter your Zerodha API Key and API Secret
   - Complete the OAuth flow
   - Your credentials will be saved to `session_data.json`

2. **After login, use curl directly:**
   ```bash
   # No authentication needed - uses stored credentials automatically
   curl -X GET \
     -H "Accept: application/json" \
     http://localhost:5001/stocks/fetch-price-websocket
   ```

**Note:** If you get a 401 error, make sure you've logged in at least once via the browser to save your credentials.

## Test with different ports (if needed)
```bash
curl -X GET http://localhost:5000/
curl -X GET http://127.0.0.1:5001/
```
