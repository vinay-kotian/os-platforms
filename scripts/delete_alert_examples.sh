#!/bin/bash

# Delete Alert API Examples
# Make sure to login first at http://localhost:5001/login

echo "🗑️  Delete Alert API Examples"
echo "=============================="

# Example 1: Delete a specific alert by UUID
echo "1. Delete alert by UUID:"
echo "curl -X DELETE http://localhost:5001/alerts/delete/b88f3994-4d51-4266-b7d4-85ac2e2f7212"
echo ""

# Example 2: Get stored alerts first to find UUIDs
echo "2. Get stored alerts to find UUIDs:"
echo "curl -X GET http://localhost:5001/alerts/stored"
echo ""

# Example 3: Delete with verbose output
echo "3. Delete with verbose output:"
echo "curl -X DELETE -v http://localhost:5001/alerts/delete/YOUR_UUID_HERE"
echo ""

# Example 4: Test with non-existent UUID
echo "4. Test with non-existent UUID:"
echo "curl -X DELETE http://localhost:5001/alerts/delete/00000000-0000-0000-0000-000000000000"
echo ""

echo "=============================="
echo "📝 Steps to test:"
echo "1. Login at http://localhost:5001/login"
echo "2. Create some alerts on the prices page"
echo "3. Get stored alerts to find UUIDs:"
echo "   curl -X GET http://localhost:5001/alerts/stored"
echo "4. Delete an alert using its UUID:"
echo "   curl -X DELETE http://localhost:5001/alerts/delete/YOUR_UUID"
echo "5. Verify deletion by getting stored alerts again"
echo ""
echo "🎯 Expected responses:"
echo "✅ Success: {\"message\": \"Alert deleted successfully\", \"success\": true}"
echo "❌ Not found: {\"error\": \"Failed to delete alert: [KITE API error]\"}"
echo "❌ Not authenticated: {\"error\": \"Not authenticated\"}"
