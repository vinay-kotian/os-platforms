# Alert API Documentation

This document describes the Alert API endpoints that allow you to create and manage alerts through the KITE API.

## Overview

The Alert API provides two main endpoints:
- `POST /alerts/create` - Create a new alert
- `GET /alerts` - Retrieve all existing alerts

## Authentication

All endpoints require authentication. You must be logged in through the web interface first:
1. Go to `http://localhost:5001/login`
2. Enter your Zerodha API credentials
3. Complete the OAuth flow
4. The session will be maintained for API calls

## Endpoints

### 1. Create Alert

**Endpoint:** `POST /alerts/create`

**Description:** Creates a new alert and sends it to the KITE API.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "name": "NIFTY 50",
    "lhs_exchange": "INDICES",
    "lhs_tradingsymbol": "NIFTY 50",
    "lhs_attribute": "LastTradedPrice",
    "operator": ">=",
    "rhs_type": "constant",
    "type": "simple",
    "rhs_constant": "27000"
}
```

**Required Fields:**
- `name` (string): Name of the alert
- `lhs_exchange` (string): Exchange for the left-hand side instrument
- `lhs_tradingsymbol` (string): Trading symbol for the left-hand side instrument
- `lhs_attribute` (string): Attribute to monitor (e.g., "LastTradedPrice")
- `operator` (string): Comparison operator (>=, <=, >, <, ==, !=)
- `rhs_type` (string): Type of right-hand side ("constant" or "variable")
- `type` (string): Alert type (e.g., "simple")

**Conditional Fields:**
- If `rhs_type` is "constant": `rhs_constant` (string/number) is required
- If `rhs_type` is "variable": `rhs_exchange`, `rhs_tradingsymbol`, `rhs_attribute` are required

**Response:**
```json
{
    "message": "Alert created successfully",
    "success": true,
    "response": {
        "alert_id": "12345"
    }
}
```

**Error Response:**
```json
{
    "error": "Missing required fields: lhs_exchange, lhs_tradingsymbol",
    "success": false
}
```

### 2. Get All Alerts

**Endpoint:** `GET /alerts`

**Description:** Retrieves all alerts from the KITE API.

**Response:**
```json
{
    "alerts": [
        {
            "id": "12345",
            "name": "NIFTY 50",
            "status": "active",
            "created_at": "2024-01-01T10:00:00Z"
        }
    ],
    "success": true
}
```

## Example Usage

### Using curl

```bash
# Create an alert
curl -X POST http://localhost:5001/alerts/create \
    -H "Content-Type: application/json" \
    -d '{
        "name": "NIFTY 50",
        "lhs_exchange": "INDICES",
        "lhs_tradingsymbol": "NIFTY 50",
        "lhs_attribute": "LastTradedPrice",
        "operator": ">=",
        "rhs_type": "constant",
        "type": "simple",
        "rhs_constant": "27000"
    }'

# Get all alerts
curl -X GET http://localhost:5001/alerts
```

### Using Python requests

```python
import requests
import json

# Create an alert
alert_data = {
    "name": "NIFTY 50",
    "lhs_exchange": "INDICES",
    "lhs_tradingsymbol": "NIFTY 50",
    "lhs_attribute": "LastTradedPrice",
    "operator": ">=",
    "rhs_type": "constant",
    "type": "simple",
    "rhs_constant": "27000"
}

response = requests.post(
    "http://localhost:5001/alerts/create",
    json=alert_data,
    headers={'Content-Type': 'application/json'}
)

print(response.json())

# Get all alerts
response = requests.get("http://localhost:5001/alerts")
print(response.json())
```

### Using JavaScript fetch

```javascript
// Create an alert
const alertData = {
    name: "NIFTY 50",
    lhs_exchange: "INDICES",
    lhs_tradingsymbol: "NIFTY 50",
    lhs_attribute: "LastTradedPrice",
    operator: ">=",
    rhs_type: "constant",
    type: "simple",
    rhs_constant: "27000"
};

fetch('http://localhost:5001/alerts/create', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(alertData)
})
.then(response => response.json())
.then(data => console.log(data));

// Get all alerts
fetch('http://localhost:5001/alerts')
.then(response => response.json())
.then(data => console.log(data));
```

## Error Codes

- `400` - Bad Request (validation errors, missing fields)
- `401` - Unauthorized (not logged in)
- `500` - Internal Server Error (KITE API errors, server errors)

## Testing

Run the test script to verify the API functionality:

```bash
python test_alert_api.py
```

**Note:** Make sure to login through the web interface first before running the tests.

## Common Use Cases

### 1. Price Alert
Alert when NIFTY 50 crosses above 27000:
```json
{
    "name": "NIFTY 50 Above 27000",
    "lhs_exchange": "INDICES",
    "lhs_tradingsymbol": "NIFTY 50",
    "lhs_attribute": "LastTradedPrice",
    "operator": ">=",
    "rhs_type": "constant",
    "type": "simple",
    "rhs_constant": "27000"
}
```

### 2. Volume Alert
Alert when trading volume exceeds a threshold:
```json
{
    "name": "High Volume Alert",
    "lhs_exchange": "NSE",
    "lhs_tradingsymbol": "RELIANCE",
    "lhs_attribute": "Volume",
    "operator": ">",
    "rhs_type": "constant",
    "type": "simple",
    "rhs_constant": "1000000"
}
```

### 3. Relative Price Alert
Alert when one stock's price is higher than another:
```json
{
    "name": "RELIANCE vs TCS",
    "lhs_exchange": "NSE",
    "lhs_tradingsymbol": "RELIANCE",
    "lhs_attribute": "LastTradedPrice",
    "operator": ">",
    "rhs_type": "variable",
    "type": "simple",
    "rhs_exchange": "NSE",
    "rhs_tradingsymbol": "TCS",
    "rhs_attribute": "LastTradedPrice"
}
```

## Notes

- All alerts are sent directly to the KITE API
- The API validates all input parameters before sending to KITE
- Authentication is required for all endpoints
- The session is maintained across requests after login
