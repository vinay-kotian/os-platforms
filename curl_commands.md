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

## Testing with verbose output
```bash
curl -v http://localhost:5001/
curl -v http://localhost:5001/prices
curl -v http://localhost:5001/stocks/fetch-price
```

## Save responses to files
```bash
curl -X GET http://localhost:5001/ -o home_page.html
curl -X GET http://localhost:5001/prices -o prices_page.html
curl -X GET http://localhost:5001/stocks/fetch-price -o stock_data.json
```

## Test with different ports (if needed)
```bash
curl -X GET http://localhost:5000/
curl -X GET http://127.0.0.1:5001/
```
