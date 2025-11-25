#!/usr/bin/env python3
"""
Test script for the Alert API
This script demonstrates how to use the alert API endpoints
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_create_alert():
    """Test creating an alert using the API"""
    
    # Example alert data matching the curl command provided
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
    
    print("Testing Alert Creation API...")
    print(f"Alert Data: {json.dumps(alert_data, indent=2)}")
    
    try:
        # Send POST request to create alert
        response = requests.post(
            f"{BASE_URL}/alerts/create",
            json=alert_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Alert created successfully!")
        else:
            print("❌ Failed to create alert")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_get_alerts():
    """Test getting all alerts using the API"""
    
    print("\nTesting Get Alerts API...")
    
    try:
        # Send GET request to fetch alerts
        response = requests.get(f"{BASE_URL}/alerts")
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Alerts fetched successfully!")
        else:
            print("❌ Failed to fetch alerts")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_alert_validation():
    """Test alert validation with invalid data"""
    
    print("\nTesting Alert Validation...")
    
    # Invalid alert data (missing required fields)
    invalid_alert_data = {
        "name": "Test Alert",
        "operator": ">=",
        "rhs_constant": "1000"
        # Missing required fields: lhs_exchange, lhs_tradingsymbol, lhs_attribute, rhs_type, type
    }
    
    print(f"Invalid Alert Data: {json.dumps(invalid_alert_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/alerts/create",
            json=invalid_alert_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 400:
            print("✅ Validation working correctly - rejected invalid data!")
        else:
            print("❌ Validation failed - should have rejected invalid data")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🚀 Alert API Test Suite")
    print("=" * 50)
    
    # Note: These tests will fail with 401 Unauthorized if not logged in
    # This is expected behavior since the API requires authentication
    
    test_create_alert()
    test_get_alerts()
    test_alert_validation()
    
    print("\n" + "=" * 50)
    print("📝 Note: These tests require authentication.")
    print("   Make sure to login through the web interface first:")
    print("   1. Go to http://localhost:5001/login")
    print("   2. Enter your Zerodha API credentials")
    print("   3. Complete the OAuth flow")
    print("   4. Then run these tests again")
