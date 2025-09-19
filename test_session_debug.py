#!/usr/bin/env python3
"""
Session Debug Test Script
This script helps debug session issues with the Alert API
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_session_status():
    """Test session status endpoint"""
    print("🔍 Testing Session Status...")
    
    try:
        response = requests.get(f"{BASE_URL}/session/status")
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        return response.json()
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def test_alert_with_debug():
    """Test alert creation with debug info"""
    print("\n🚨 Testing Alert Creation with Debug...")
    
    alert_data = {
        "name": "NIFTY 50 Debug Test",
        "lhs_exchange": "INDICES",
        "lhs_tradingsymbol": "NIFTY 50",
        "lhs_attribute": "LastTradedPrice",
        "operator": ">=",
        "rhs_type": "constant",
        "type": "simple",
        "rhs_constant": "27000"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/alerts/create",
            json=alert_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 401:
            print("\n🔍 Debug Info from 401 response:")
            debug_info = response.json().get('debug', {})
            for key, value in debug_info.items():
                print(f"  {key}: {value}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_working_endpoint():
    """Test a working endpoint to compare"""
    print("\n✅ Testing Working Endpoint (prices)...")
    
    try:
        response = requests.get(f"{BASE_URL}/stocks/fetch-price")
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Prices endpoint works - session is working for other endpoints")
        elif response.status_code == 401:
            print("❌ Prices endpoint also returns 401 - session issue is global")
        else:
            print(f"⚠️  Prices endpoint returned: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🔍 Session Debug Tool")
    print("=" * 50)
    
    # Test session status
    session_info = test_session_status()
    
    # Test working endpoint
    test_working_endpoint()
    
    # Test alert creation
    test_alert_with_debug()
    
    print("\n" + "=" * 50)
    print("📝 Analysis:")
    
    if session_info:
        session_data = session_info.get('session_data', {})
        global_data = session_info.get('global_data', {})
        
        print(f"  Session has access_token: {bool(session_data.get('access_token'))}")
        print(f"  Global kite initialized: {global_data.get('kite_initialized')}")
        print(f"  Session file exists: {session_info.get('file_exists')}")
        
        if not session_data.get('access_token'):
            print("\n❌ Issue: Session doesn't have access_token")
            print("   Solution: Login at http://localhost:5001/login")
        elif not global_data.get('kite_initialized'):
            print("\n❌ Issue: Global kite object not initialized")
            print("   Solution: Restart the Flask app")
        else:
            print("\n✅ Session appears to be working correctly")
