#!/bin/bash

# Test Alert API with curl commands
# Make sure to login first at http://localhost:5001/login

echo "🔍 Testing Alert API with curl"
echo "================================"

# Test 1: Check if server is running
echo "1. Testing server status..."
curl -s -o /dev/null -w "Server Status: %{http_code}\n" http://localhost:5001/

# Test 2: Check authentication (should return 401 if not logged in)
echo -e "\n2. Testing authentication..."
curl -s -w "Auth Status: %{http_code}\n" http://localhost:5001/stocks/fetch-price

# Test 3: Create an alert (will fail if not authenticated)
echo -e "\n3. Testing alert creation..."
curl -X POST http://localhost:5001/alerts/create \
    -H "Content-Type: application/json" \
    -d '{
        "name": "NIFTY 50 Test",
        "lhs_exchange": "INDICES",
        "lhs_tradingsymbol": "NIFTY 50",
        "lhs_attribute": "LastTradedPrice",
        "operator": ">=",
        "rhs_type": "constant",
        "type": "simple",
        "rhs_constant": "27000"
    }' \
    -w "\nAlert Creation Status: %{http_code}\n"

# Test 4: Get all alerts
echo -e "\n4. Testing get alerts..."
curl -s -w "Get Alerts Status: %{http_code}\n" http://localhost:5001/alerts

echo -e "\n================================"
echo "📝 If you see 401 errors, please login first:"
echo "   Go to http://localhost:5001/login"
echo "   Enter your Zerodha API credentials"
echo "   Complete the OAuth flow"
