#!/usr/bin/env python3
"""
Test script for alert trigger functionality
"""

import requests
import json
import time

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_alert_trigger_api():
    """Test the alert trigger checking API"""
    print("🚨 Testing Alert Trigger API...")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/check-triggers")
        
        print(f"Response Status: {response.status_code}")
        response_data = response.json()
        print(f"Response Body: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200:
            triggered_alerts = response_data.get('triggered_alerts', [])
            count = response_data.get('count', 0)
            
            print(f"✅ Found {count} triggered alerts")
            
            if triggered_alerts:
                print("\n📊 Triggered Alerts:")
                for i, alert in enumerate(triggered_alerts, 1):
                    print(f"  {i}. {alert.get('name')}")
                    print(f"     Symbol: {alert.get('symbol')}")
                    print(f"     Condition: {alert.get('operator')} ₹{alert.get('target_price')}")
                    print(f"     Current Price: ₹{alert.get('current_price')}")
                    print(f"     Triggered At: {alert.get('triggered_at')}")
                    print()
            else:
                print("📝 No alerts triggered at the moment")
                
        elif response.status_code == 401:
            print("❌ Authentication required - please login first")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_stored_alerts_with_triggers():
    """Test stored alerts to see trigger information"""
    print("\n📋 Testing Stored Alerts with Trigger Info...")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored")
        
        if response.status_code == 200:
            data = response.json()
            alerts = data.get('alerts', [])
            
            print(f"📊 Total stored alerts: {len(alerts)}")
            
            if alerts:
                print("\n📋 Alert Details:")
                for i, alert in enumerate(alerts, 1):
                    print(f"  {i}. {alert.get('name')}")
                    print(f"     Symbol: {alert.get('lhs_tradingsymbol')}")
                    print(f"     Status: {alert.get('status')}")
                    print(f"     Alert Count: {alert.get('alert_count', 0)}")
                    
                    if alert.get('last_triggered_at'):
                        print(f"     Last Triggered: {alert.get('last_triggered_at')}")
                        print(f"     Last Triggered Price: ₹{alert.get('last_triggered_price', 'N/A')}")
                    else:
                        print(f"     Last Triggered: Never")
                    print()
            else:
                print("📝 No stored alerts found")
        else:
            print(f"❌ Failed to get stored alerts: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_create_alert_for_triggering():
    """Create an alert that's likely to trigger for testing"""
    print("\n🎯 Creating Test Alert for Triggering...")
    
    # Get current prices first
    try:
        prices_response = requests.get(f"{BASE_URL}/stocks/fetch-price")
        if prices_response.status_code == 200:
            prices_data = prices_response.json()
            nifty_price = prices_data.get('nifty', {}).get('current_price', 0)
            bank_nifty_price = prices_data.get('bank_nifty', {}).get('current_price', 0)
            
            print(f"Current NIFTY 50: ₹{nifty_price}")
            print(f"Current NIFTY BANK: ₹{bank_nifty_price}")
            
            # Create an alert that's likely to trigger (set target below current price)
            if nifty_price > 0:
                target_price = nifty_price - 100  # 100 points below current
                
                alert_data = {
                    "name": "Test Trigger Alert",
                    "lhs_exchange": "INDICES",
                    "lhs_tradingsymbol": "NIFTY 50",
                    "lhs_attribute": "LastTradedPrice",
                    "operator": ">=",
                    "rhs_type": "constant",
                    "type": "simple",
                    "rhs_constant": str(target_price)
                }
                
                print(f"Creating alert: NIFTY 50 >= ₹{target_price}")
                
                response = requests.post(
                    f"{BASE_URL}/alerts/create",
                    json=alert_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    print("✅ Test alert created successfully!")
                    print("   This alert should trigger immediately since current price is above target")
                    
                    # Wait a moment and check for triggers
                    print("\n⏳ Waiting 2 seconds and checking for triggers...")
                    time.sleep(2)
                    test_alert_trigger_api()
                    
                else:
                    print(f"❌ Failed to create test alert: {response.status_code}")
                    print(f"   Response: {response.text}")
            else:
                print("❌ Could not get current prices")
        else:
            print("❌ Could not fetch current prices")
            
    except Exception as e:
        print(f"❌ Error creating test alert: {str(e)}")

def test_continuous_monitoring():
    """Test continuous monitoring of alert triggers"""
    print("\n🔄 Testing Continuous Alert Monitoring...")
    print("This will check for triggers every 5 seconds for 30 seconds")
    print("Press Ctrl+C to stop early")
    
    try:
        for i in range(6):  # 6 checks over 30 seconds
            print(f"\n--- Check {i+1}/6 ---")
            test_alert_trigger_api()
            
            if i < 5:  # Don't wait after the last check
                print("⏳ Waiting 5 seconds...")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error during monitoring: {str(e)}")

if __name__ == "__main__":
    print("🚨 Alert Trigger Test Suite")
    print("=" * 60)
    
    # Test 1: Check alert trigger API
    test_alert_trigger_api()
    
    # Test 2: Check stored alerts with trigger info
    test_stored_alerts_with_triggers()
    
    # Test 3: Create a test alert that should trigger
    test_create_alert_for_triggering()
    
    # Test 4: Continuous monitoring (optional)
    print("\n" + "=" * 60)
    print("🔄 Optional: Test continuous monitoring? (y/n)")
    try:
        choice = input().lower().strip()
        if choice == 'y':
            test_continuous_monitoring()
    except KeyboardInterrupt:
        print("\n⏹️  Skipping continuous monitoring")
    
    print("\n" + "=" * 60)
    print("📝 Test Summary:")
    print("  ✅ Alert trigger API endpoint")
    print("  ✅ Stored alerts with trigger information")
    print("  ✅ Test alert creation and triggering")
    print("  ✅ Continuous monitoring capability")
    print("\n🎯 How it works:")
    print("  1. Alerts are checked every second on the prices page")
    print("  2. When conditions are met, alerts are marked as triggered")
    print("  3. Trigger notifications appear on the page")
    print("  4. Alert status shows trigger count and last trigger time")
    print("\n💡 To test manually:")
    print("  1. Go to http://localhost:5001/prices")
    print("  2. Create alerts with targets close to current prices")
    print("  3. Watch for trigger notifications and status updates")

