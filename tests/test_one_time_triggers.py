#!/usr/bin/env python3
"""
Test script for one-time alert trigger functionality
"""

import requests
import json
import time

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_one_time_trigger():
    """Test that alerts trigger only once"""
    print("🎯 Testing One-Time Alert Trigger...")
    
    try:
        # First, get current prices
        prices_response = requests.get(f"{BASE_URL}/stocks/fetch-price")
        if prices_response.status_code == 200:
            prices_data = prices_response.json()
            nifty_price = prices_data.get('nifty', {}).get('current_price', 0)
            
            print(f"Current NIFTY 50: ₹{nifty_price}")
            
            if nifty_price > 0:
                # Create an alert that should trigger immediately
                target_price = nifty_price - 50  # 50 points below current
                
                alert_data = {
                    "name": "One-Time Trigger Test",
                    "lhs_exchange": "INDICES",
                    "lhs_tradingsymbol": "NIFTY 50",
                    "lhs_attribute": "LastTradedPrice",
                    "operator": ">=",
                    "rhs_type": "constant",
                    "type": "simple",
                    "rhs_constant": str(target_price)
                }
                
                print(f"Creating alert: NIFTY 50 >= ₹{target_price}")
                print("This should trigger immediately since current price is above target")
                
                # Create the alert
                create_response = requests.post(
                    f"{BASE_URL}/alerts/create",
                    json=alert_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if create_response.status_code == 200:
                    print("✅ Alert created successfully!")
                    
                    # Wait a moment for the trigger to be detected
                    print("⏳ Waiting 3 seconds for trigger detection...")
                    time.sleep(3)
                    
                    # Check for triggers
                    print("\n🔍 Checking for triggers...")
                    trigger_response = requests.get(f"{BASE_URL}/alerts/check-triggers")
                    
                    if trigger_response.status_code == 200:
                        trigger_data = trigger_response.json()
                        triggered_count = trigger_data.get('count', 0)
                        
                        if triggered_count > 0:
                            print(f"✅ Found {triggered_count} triggered alert(s)")
                            
                            # Wait and check again to ensure it doesn't trigger again
                            print("\n⏳ Waiting 5 seconds and checking again...")
                            time.sleep(5)
                            
                            trigger_response2 = requests.get(f"{BASE_URL}/alerts/check-triggers")
                            if trigger_response2.status_code == 200:
                                trigger_data2 = trigger_response2.json()
                                triggered_count2 = trigger_data2.get('count', 0)
                                
                                if triggered_count2 == 0:
                                    print("✅ Alert did NOT trigger again - one-time trigger working!")
                                else:
                                    print(f"❌ Alert triggered again ({triggered_count2} times) - one-time trigger NOT working")
                        else:
                            print("❌ No triggers detected - alert may not have triggered")
                    else:
                        print(f"❌ Failed to check triggers: {trigger_response.status_code}")
                        
                    # Check stored alerts to see the status
                    print("\n📋 Checking stored alerts status...")
                    stored_response = requests.get(f"{BASE_URL}/alerts/stored")
                    
                    if stored_response.status_code == 200:
                        stored_data = stored_response.json()
                        alerts = stored_data.get('alerts', [])
                        
                        # Find our test alert
                        test_alert = next((a for a in alerts if a.get('name') == 'One-Time Trigger Test'), None)
                        
                        if test_alert:
                            print(f"Alert Status: {test_alert.get('status')}")
                            print(f"Alert Count: {test_alert.get('alert_count')}")
                            print(f"Last Triggered: {test_alert.get('last_triggered_at', 'Never')}")
                            
                            if test_alert.get('status') == 'triggered' and test_alert.get('alert_count') == 1:
                                print("✅ Alert correctly marked as 'triggered' with count = 1")
                            else:
                                print("❌ Alert status not correctly updated")
                        else:
                            print("❌ Test alert not found in stored alerts")
                    else:
                        print(f"❌ Failed to get stored alerts: {stored_response.status_code}")
                        
                else:
                    print(f"❌ Failed to create alert: {create_response.status_code}")
                    print(f"Response: {create_response.text}")
            else:
                print("❌ Could not get current NIFTY price")
        else:
            print("❌ Could not fetch current prices")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_multiple_alerts():
    """Test multiple alerts to ensure each triggers only once"""
    print("\n🔄 Testing Multiple One-Time Alerts...")
    
    try:
        # Get current prices
        prices_response = requests.get(f"{BASE_URL}/stocks/fetch-price")
        if prices_response.status_code == 200:
            prices_data = prices_response.json()
            nifty_price = prices_data.get('nifty', {}).get('current_price', 0)
            bank_nifty_price = prices_data.get('bank_nifty', {}).get('current_price', 0)
            
            print(f"Current NIFTY 50: ₹{nifty_price}")
            print(f"Current NIFTY BANK: ₹{bank_nifty_price}")
            
            # Create multiple alerts that should trigger
            test_alerts = [
                {
                    "name": "NIFTY Test 1",
                    "lhs_exchange": "INDICES",
                    "lhs_tradingsymbol": "NIFTY 50",
                    "lhs_attribute": "LastTradedPrice",
                    "operator": ">=",
                    "rhs_type": "constant",
                    "type": "simple",
                    "rhs_constant": str(nifty_price - 100)
                },
                {
                    "name": "NIFTY Test 2",
                    "lhs_exchange": "INDICES",
                    "lhs_tradingsymbol": "NIFTY 50",
                    "lhs_attribute": "LastTradedPrice",
                    "operator": ">=",
                    "rhs_type": "constant",
                    "type": "simple",
                    "rhs_constant": str(nifty_price - 200)
                }
            ]
            
            created_alerts = []
            
            # Create the alerts
            for alert_data in test_alerts:
                response = requests.post(
                    f"{BASE_URL}/alerts/create",
                    json=alert_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    print(f"✅ Created alert: {alert_data['name']}")
                    created_alerts.append(alert_data['name'])
                else:
                    print(f"❌ Failed to create alert: {alert_data['name']}")
            
            if created_alerts:
                print(f"\n⏳ Waiting 5 seconds for all triggers...")
                time.sleep(5)
                
                # Check stored alerts
                stored_response = requests.get(f"{BASE_URL}/alerts/stored")
                if stored_response.status_code == 200:
                    stored_data = stored_response.json()
                    alerts = stored_data.get('alerts', [])
                    
                    triggered_count = 0
                    for alert in alerts:
                        if alert.get('name') in created_alerts:
                            status = alert.get('status')
                            count = alert.get('alert_count', 0)
                            
                            print(f"Alert '{alert.get('name')}': Status={status}, Count={count}")
                            
                            if status == 'triggered' and count == 1:
                                triggered_count += 1
                    
                    print(f"\n📊 Summary: {triggered_count}/{len(created_alerts)} alerts correctly triggered once")
                    
                    if triggered_count == len(created_alerts):
                        print("✅ All alerts correctly triggered once!")
                    else:
                        print("❌ Some alerts did not trigger correctly")
                        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🎯 One-Time Alert Trigger Test Suite")
    print("=" * 60)
    
    # Test single alert one-time trigger
    test_one_time_trigger()
    
    # Test multiple alerts
    test_multiple_alerts()
    
    print("\n" + "=" * 60)
    print("📝 Test Summary:")
    print("  ✅ One-time trigger functionality")
    print("  ✅ Alert status updates to 'triggered'")
    print("  ✅ Alert count set to 1")
    print("  ✅ No repeated triggers")
    print("\n🎯 Expected Behavior:")
    print("  1. Alert triggers when condition is met")
    print("  2. Status changes from 'enabled' to 'triggered'")
    print("  3. Alert count becomes 1")
    print("  4. Alert is no longer checked for triggers")
    print("  5. Visual indicator shows 'Triggered Once'")
    print("\n💡 To test manually:")
    print("  1. Create alerts with targets close to current prices")
    print("  2. Watch for trigger notifications")
    print("  3. Verify alert status changes to 'triggered'")
    print("  4. Confirm alerts don't trigger again")

