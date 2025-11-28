#!/bin/bash
# Helper script to set entry prices for trade execution

echo "Setting Entry Prices for Trade Execution"
echo "========================================"
echo ""

# Get current prices
echo "Fetching current prices..."
NIFTY_PRICE=$(curl -s http://localhost:5001/trading/get-trend | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['trends']['NIFTY_50']['current_price'])")
BANK_PRICE=$(curl -s http://localhost:5001/trading/get-trend | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['trends']['NIFTY_BANK']['current_price'])")

echo "Current NIFTY 50 price: ₹${NIFTY_PRICE}"
echo "Current NIFTY BANK price: ₹${BANK_PRICE}"
echo ""

# Set entry prices (using current prices as example)
echo "Setting entry prices..."
echo ""

# Set NIFTY 50 entry price
echo "Setting NIFTY 50 entry price to ₹${NIFTY_PRICE}..."
curl -X POST http://localhost:5001/trading/set-entry-price \
  -H 'Content-Type: application/json' \
  -d "{\"instrument\": \"NIFTY_50\", \"entry_price\": ${NIFTY_PRICE}}" | python3 -m json.tool

echo ""

# Set NIFTY BANK entry price  
echo "Setting NIFTY BANK entry price to ₹${BANK_PRICE}..."
curl -X POST http://localhost:5001/trading/set-entry-price \
  -H 'Content-Type: application/json' \
  -d "{\"instrument\": \"NIFTY_BANK\", \"entry_price\": ${BANK_PRICE}}" | python3 -m json.tool

echo ""
echo "✅ Entry prices set!"
echo ""
echo "The system will now monitor for price touches and execute trades when:"
echo "  - Price comes from above and touches entry level → CALL order"
echo "  - Price comes from below and touches entry level → PUT order"
echo ""
echo "Note: Price must be within 0.1% tolerance of entry level to trigger."


