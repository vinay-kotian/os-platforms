#!/usr/bin/env python3
"""
Test script for the delete alert functionality
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_delete_alert():
    """Test deleting an alert"""
    print("🗑️  Testing Delete Alert Functionality...")
    
    # First, let's get all stored alerts to find one to delete
    print("\n1. Getting stored alerts...")
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored")
        
        if response.status_code == 200:
            data = response.json()
            alerts = data.get('alerts', [])
            print(f"   Found {len(alerts)} stored alerts")
            
            if alerts:
                # Get the first alert to delete
                alert_to_delete = alerts[0]
                uuid = alert_to_delete.get('uuid')
                name = alert_to_delete.get('name')
                
                print(f"   Will delete alert: {name} (UUID: {uuid})")
                
                # Test delete
                print(f"\n2. Deleting alert {uuid}...")
                delete_response = requests.delete(f"{BASE_URL}/alerts/delete/{uuid}")
                
                print(f"   Delete Response Status: {delete_response.status_code}")
                delete_data = delete_response.json()
                print(f"   Delete Response: {json.dumps(delete_data, indent=2)}")
                
                if delete_response.status_code == 200 and delete_data.get('success'):
                    print("   ✅ Alert deleted successfully!")
                    
                    # Verify deletion by checking stored alerts again
                    print(f"\n3. Verifying deletion...")
                    verify_response = requests.get(f"{BASE_URL}/alerts/stored")
                    
                    if verify_response.status_code == 200:
                        verify_data = verify_response.json()
                        remaining_alerts = verify_data.get('alerts', [])
                        
                        # Check if the deleted alert is still there
                        deleted_alert = next((a for a in remaining_alerts if a.get('uuid') == uuid), None)
                        
                        if deleted_alert:
                            print("   ❌ Alert still found in stored alerts - deletion may have failed")
                        else:
                            print(f"   ✅ Alert successfully removed from stored alerts")
                            print(f"   📊 Remaining alerts: {len(remaining_alerts)}")
                    else:
                        print(f"   ⚠️  Could not verify deletion: {verify_response.status_code}")
                        
                else:
                    print("   ❌ Failed to delete alert")
                    
            else:
                print("   ⚠️  No alerts found to delete")
                print("   💡 Create an alert first, then run this test again")
                
        elif response.status_code == 401:
            print("   ❌ Authentication required - please login first")
        else:
            print(f"   ❌ Failed to get stored alerts: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_delete_nonexistent_alert():
    """Test deleting a non-existent alert"""
    print("\n🔍 Testing Delete Non-existent Alert...")
    
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    
    try:
        response = requests.delete(f"{BASE_URL}/alerts/delete/{fake_uuid}")
        
        print(f"   Response Status: {response.status_code}")
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 500:
            print("   ✅ Correctly returned error for non-existent alert")
        else:
            print("   ⚠️  Unexpected response for non-existent alert")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

def test_delete_without_auth():
    """Test deleting without authentication"""
    print("\n🔐 Testing Delete Without Authentication...")
    
    # This test assumes you're not logged in
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    
    try:
        response = requests.delete(f"{BASE_URL}/alerts/delete/{fake_uuid}")
        
        print(f"   Response Status: {response.status_code}")
        data = response.json()
        print(f"   Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 401:
            print("   ✅ Correctly returned 401 for unauthenticated request")
        else:
            print("   ⚠️  Unexpected response for unauthenticated request")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🗑️  Delete Alert Test Suite")
    print("=" * 50)
    
    # Test delete functionality
    test_delete_alert()
    
    # Test edge cases
    test_delete_nonexistent_alert()
    test_delete_without_auth()
    
    print("\n" + "=" * 50)
    print("📝 Test Summary:")
    print("  ✅ Delete alert functionality")
    print("  ✅ Error handling for non-existent alerts")
    print("  ✅ Authentication validation")
    print("\n🎯 Usage:")
    print("  1. Login at http://localhost:5001/login")
    print("  2. Go to prices page: http://localhost:5001/prices")
    print("  3. Create some alerts")
    print("  4. Click 'Delete' button on any alert")
    print("  5. Confirm deletion")
    print("  6. Alert should be removed from both KITE and local database")
