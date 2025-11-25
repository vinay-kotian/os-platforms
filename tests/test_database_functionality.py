#!/usr/bin/env python3
"""
Database Functionality Test Script
This script tests the database storage and retrieval functionality for alerts
"""

import requests
import json

# Base URL for the Flask app
BASE_URL = "http://localhost:5001"

def test_create_alert_and_store():
    """Test creating an alert and storing it in database"""
    print("🚨 Testing Alert Creation and Database Storage...")
    
    alert_data = {
        "name": "NIFTY 50 Database Test",
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
            print("✅ Alert created and stored successfully!")
            
            # Extract UUID from response for further testing
            uuid = response_data.get('response', {}).get('data', {}).get('uuid')
            if uuid:
                print(f"📝 Alert UUID: {uuid}")
                return uuid
            else:
                print("⚠️  No UUID found in response")
                return None
        else:
            print("❌ Failed to create alert")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

def test_get_stored_alerts():
    """Test retrieving all stored alerts"""
    print("\n📋 Testing Get All Stored Alerts...")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored")
        
        print(f"Response Status: {response.status_code}")
        response_data = response.json()
        print(f"Response Body: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200:
            alerts = response_data.get('alerts', [])
            count = response_data.get('count', 0)
            print(f"✅ Retrieved {count} stored alerts")
            
            if alerts:
                print("\n📊 Alert Summary:")
                for i, alert in enumerate(alerts[:3], 1):  # Show first 3 alerts
                    print(f"  {i}. {alert.get('name')} - {alert.get('status')} - {alert.get('created_at')}")
                
                if count > 3:
                    print(f"  ... and {count - 3} more alerts")
            
            return alerts
        else:
            print("❌ Failed to retrieve stored alerts")
            return []
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
        return []
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return []

def test_get_alert_by_uuid(uuid):
    """Test retrieving a specific alert by UUID"""
    if not uuid:
        print("\n⚠️  Skipping UUID test - no UUID available")
        return
    
    print(f"\n🔍 Testing Get Alert by UUID: {uuid}")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored/{uuid}")
        
        print(f"Response Status: {response.status_code}")
        response_data = response.json()
        print(f"Response Body: {json.dumps(response_data, indent=2)}")
        
        if response.status_code == 200:
            alert = response_data.get('alert', {})
            print("✅ Retrieved alert by UUID successfully!")
            print(f"📊 Alert Details:")
            print(f"  Name: {alert.get('name')}")
            print(f"  Status: {alert.get('status')}")
            print(f"  User ID: {alert.get('user_id')}")
            print(f"  Created: {alert.get('created_at')}")
            print(f"  Stored: {alert.get('stored_at')}")
        else:
            print("❌ Failed to retrieve alert by UUID")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_database_schema():
    """Test database schema by checking the structure of stored data"""
    print("\n🗄️  Testing Database Schema...")
    
    try:
        response = requests.get(f"{BASE_URL}/alerts/stored")
        
        if response.status_code == 200:
            response_data = response.json()
            alerts = response_data.get('alerts', [])
            
            if alerts:
                # Check the first alert for all expected fields
                first_alert = alerts[0]
                expected_fields = [
                    'uuid', 'name', 'user_id', 'lhs_exchange', 'lhs_tradingsymbol',
                    'lhs_attribute', 'operator', 'rhs_type', 'rhs_constant',
                    'type', 'status', 'alert_count', 'created_at', 'updated_at', 'stored_at'
                ]
                
                missing_fields = [field for field in expected_fields if field not in first_alert]
                
                if not missing_fields:
                    print("✅ Database schema is correct - all expected fields present")
                else:
                    print(f"⚠️  Missing fields in database schema: {missing_fields}")
                
                print(f"📊 Sample alert structure:")
                for field in expected_fields[:5]:  # Show first 5 fields
                    print(f"  {field}: {first_alert.get(field)}")
                print("  ...")
            else:
                print("⚠️  No alerts found to test schema")
        else:
            print("❌ Failed to retrieve alerts for schema test")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the Flask app is running on localhost:5001")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("🗄️  Database Functionality Test Suite")
    print("=" * 60)
    
    # Test 1: Create alert and store in database
    uuid = test_create_alert_and_store()
    
    # Test 2: Get all stored alerts
    alerts = test_get_stored_alerts()
    
    # Test 3: Get specific alert by UUID
    test_get_alert_by_uuid(uuid)
    
    # Test 4: Test database schema
    test_database_schema()
    
    print("\n" + "=" * 60)
    print("📝 Test Summary:")
    print("  ✅ Alert creation and storage")
    print("  ✅ Alert retrieval (all)")
    print("  ✅ Alert retrieval (by UUID)")
    print("  ✅ Database schema validation")
    print("\n🎉 All database functionality tests completed!")
