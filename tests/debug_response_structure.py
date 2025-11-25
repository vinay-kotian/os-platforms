#!/usr/bin/env python3
"""
Debug script to test response structure handling
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_alert_creation_with_debug():
    """Test alert creation and debug the response structure"""
    print("🚨 Testing Alert Creation with Response Debug...")
    
    alert_data = {
        "name": "NIFTY 50 Response Debug Test",
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
        response_data = response.json()
        print(f"Response Body: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Alert created successfully!")
            
            # Check the response structure
            print("\n🔍 Analyzing Response Structure:")
            
            if 'response' in response_data:
                print("  ✅ 'response' key found")
                if 'data' in response_data['response']:
                    print("  ✅ 'data' key found in response")
                    data = response_data['response']['data']
                    print(f"  📊 Data keys: {list(data.keys())}")
                    
                    if 'uuid' in data:
                        print(f"  ✅ UUID found: {data['uuid']}")
                    else:
                        print("  ❌ UUID not found in data")
                else:
                    print("  ❌ 'data' key not found in response")
            else:
                print("  ❌ 'response' key not found")
                print(f"  📊 Top-level keys: {list(response_data.keys())}")
            
            return response_data
        else:
            print("❌ Failed to create alert")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def check_database_after_creation():
    """Check if alert was stored in database"""
    print("\n🗄️  Checking Database After Alert Creation...")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored")
        
        if response.status_code == 200:
            data = response.json()
            alerts = data.get('alerts', [])
            count = data.get('count', 0)
            
            print(f"📊 Database Status: {count} alerts stored")
            
            if alerts:
                print("\n📋 Stored Alerts:")
                for i, alert in enumerate(alerts[:3], 1):
                    print(f"  {i}. {alert.get('name')} - UUID: {alert.get('uuid')}")
            else:
                print("❌ No alerts found in database")
                print("   This suggests the database storage failed")
        else:
            print(f"❌ Failed to check database: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking database: {str(e)}")

if __name__ == "__main__":
    print("🔍 Response Structure Debug Tool")
    print("=" * 60)
    
    # Test alert creation
    response_data = test_alert_creation_with_debug()
    
    # Check database
    check_database_after_creation()
    
    print("\n" + "=" * 60)
    print("📝 Next Steps:")
    print("   1. Check the Flask app console for debug output")
    print("   2. Look for 'Debug - KITE response structure' messages")
    print("   3. Verify the response structure matches expectations")
    print("   4. Check if database storage succeeded")
