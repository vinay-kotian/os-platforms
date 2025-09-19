#!/usr/bin/env python3
"""
Debug script for the Alert API
This script helps debug authentication and API issues
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_authentication():
    """Test if the user is authenticated"""
    print("🔐 Testing Authentication...")
    
    try:
        # Test the prices endpoint first (requires auth)
        response = requests.get(f"{BASE_URL}/stocks/fetch-price")
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ User is authenticated!")
            return True
        elif response.status_code == 401:
            print("❌ User is NOT authenticated")
            print("   Please login at: http://localhost:5001/login")
            return False
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_alert_creation():
    """Test alert creation with detailed debugging"""
    print("\n🚨 Testing Alert Creation...")
    
    # Example alert data
    alert_data = {
        "name": "NIFTY 50 Test",
        "lhs_exchange": "INDICES",
        "lhs_tradingsymbol": "NIFTY 50",
        "lhs_attribute": "LastTradedPrice",
        "operator": ">=",
        "rhs_type": "constant",
        "type": "simple",
        "rhs_constant": "27000"
    }
    
    print(f"Alert Data: {json.dumps(alert_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/alerts/create",
            json=alert_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Alert created successfully!")
        elif response.status_code == 401:
            print("❌ Authentication failed - please login first")
        elif response.status_code == 400:
            print("❌ Bad request - check your alert data")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_server_status():
    """Test if the server is running"""
    print("🌐 Testing Server Status...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Server Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Server is running!")
            return True
        else:
            print(f"⚠️  Server responded with: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running or not accessible")
        print("   Start the server with: python app.py")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Alert API Debug Tool")
    print("=" * 50)
    
    # Test server status first
    if not test_server_status():
        print("\n❌ Cannot proceed - server is not running")
        exit(1)
    
    # Test authentication
    is_authenticated = test_authentication()
    
    # Test alert creation
    test_alert_creation()
    
    print("\n" + "=" * 50)
    if not is_authenticated:
        print("📝 Next Steps:")
        print("   1. Go to http://localhost:5001/login")
        print("   2. Enter your Zerodha API credentials")
        print("   3. Complete the OAuth flow")
        print("   4. Run this script again")
    else:
        print("✅ All tests completed!")
