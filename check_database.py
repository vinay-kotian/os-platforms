#!/usr/bin/env python3
"""
Quick script to check if alerts are being saved in the database
"""

import sqlite3
import os
import json

DATABASE_FILE = 'app.db'

def check_database():
    """Check if database exists and has alerts"""
    print("🔍 Checking Database Status...")
    
    # Check if database file exists
    if not os.path.exists(DATABASE_FILE):
        print(f"❌ Database file '{DATABASE_FILE}' does not exist")
        print("   This means no alerts have been created yet")
        return
    
    print(f"✅ Database file '{DATABASE_FILE}' exists")
    
    try:
        # Connect to database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if alerts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ 'alerts' table does not exist")
            print("   Database was not properly initialized")
            conn.close()
            return
        
        print("✅ 'alerts' table exists")
        
        # Count alerts
        cursor.execute("SELECT COUNT(*) FROM alerts")
        count = cursor.fetchone()[0]
        print(f"📊 Total alerts in database: {count}")
        
        if count > 0:
            # Show recent alerts
            cursor.execute('''
                SELECT uuid, name, status, created_at, stored_at
                FROM alerts
                ORDER BY stored_at DESC
                LIMIT 5
            ''')
            
            alerts = cursor.fetchall()
            print("\n📋 Recent Alerts:")
            for i, alert in enumerate(alerts, 1):
                uuid, name, status, created_at, stored_at = alert
                print(f"  {i}. {name}")
                print(f"     UUID: {uuid}")
                print(f"     Status: {status}")
                print(f"     Created: {created_at}")
                print(f"     Stored: {stored_at}")
                print()
        else:
            print("📝 No alerts found in database")
            print("   Try creating an alert first")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

def check_database_schema():
    """Check the database schema"""
    print("\n🗄️  Checking Database Schema...")
    
    if not os.path.exists(DATABASE_FILE):
        print("❌ Database file does not exist")
        return
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(alerts)")
        columns = cursor.fetchall()
        
        print("📊 Alerts Table Schema:")
        for col in columns:
            col_id, name, data_type, not_null, default, pk = col
            print(f"  {name}: {data_type} {'(PRIMARY KEY)' if pk else ''} {'NOT NULL' if not_null else ''}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking schema: {e}")

if __name__ == "__main__":
    print("🗄️  Database Check Tool")
    print("=" * 50)
    
    check_database()
    check_database_schema()
    
    print("\n" + "=" * 50)
    print("📝 To test alert storage:")
    print("   1. Make sure Flask app is running")
    print("   2. Login at http://localhost:5001/login")
    print("   3. Create an alert using the API")
    print("   4. Run this script again to verify storage")
