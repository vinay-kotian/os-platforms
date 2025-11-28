#!/usr/bin/env python3
"""
Diagnostic script to check why trades aren't executing
"""
import sqlite3
import sys
import os

# Add the project directory to path to import services
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATABASE_FILE = 'app.db'

def check_entry_prices():
    """Check if entry prices are set"""
    print("=" * 80)
    print("CHECKING ENTRY PRICES")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM entry_prices')
        rows = cursor.fetchall()
        
        if rows:
            print("\n✅ Entry prices found in database:")
            for row in rows:
                print(f"  - {row[2]}: ₹{row[3]}")
        else:
            print("\n❌ NO ENTRY PRICES SET IN DATABASE!")
            print("   You need to set entry prices using the /trading/set-entry-price API")
            print("   Example:")
            print("   curl -X POST http://localhost:5001/trading/set-entry-price \\")
            print("     -H 'Content-Type: application/json' \\")
            print("     -d '{\"instrument\": \"NIFTY_50\", \"entry_price\": 25000}'")
        
        conn.close()
        return len(rows) > 0
        
    except Exception as e:
        print(f"\n❌ Error checking entry prices: {e}")
        return False

def check_price_data():
    """Check if price data is being collected"""
    print("\n" + "=" * 80)
    print("CHECKING PRICE DATA COLLECTION")
    print("=" * 80)
    
    try:
        # Try to import and check services
        from services import (
            nifty_prices, bank_nifty_prices, 
            entry_prices_cache, 
            previous_price_position,
            order_placed_at_level,
            trend_monitoring_running,
            websocket_prices
        )
        
        print(f"\n📊 NIFTY 50 prices in deque: {len(nifty_prices)}")
        if len(nifty_prices) > 0:
            print(f"   Latest price: ₹{list(nifty_prices)[-1]:.2f}")
        else:
            print("   ⚠️  No prices collected yet!")
        
        print(f"\n📊 NIFTY BANK prices in deque: {len(bank_nifty_prices)}")
        if len(bank_nifty_prices) > 0:
            print(f"   Latest price: ₹{list(bank_nifty_prices)[-1]:.2f}")
        else:
            print("   ⚠️  No prices collected yet!")
        
        print(f"\n💰 Entry prices in cache:")
        print(f"   NIFTY_50: {entry_prices_cache.get('NIFTY_50', 'NOT SET')}")
        print(f"   NIFTY_BANK: {entry_prices_cache.get('NIFTY_BANK', 'NOT SET')}")
        
        print(f"\n📍 Previous price positions:")
        print(f"   NIFTY_50: {previous_price_position.get('NIFTY_50', 'NOT SET')}")
        print(f"   NIFTY_BANK: {previous_price_position.get('NIFTY_BANK', 'NOT SET')}")
        
        print(f"\n🚫 Order placed flags:")
        print(f"   NIFTY_50: {order_placed_at_level.get('NIFTY_50', False)}")
        print(f"   NIFTY_BANK: {order_placed_at_level.get('NIFTY_BANK', False)}")
        
        print(f"\n🔄 Trend monitoring running: {trend_monitoring_running}")
        
        print(f"\n📡 WebSocket prices:")
        print(f"   NIFTY 50: ₹{websocket_prices['NIFTY 50'].get('last_price', 0):.2f}")
        print(f"   NIFTY BANK: ₹{websocket_prices['NIFTY BANK'].get('last_price', 0):.2f}")
        
        # Check if prices are near entry levels
        if entry_prices_cache.get('NIFTY_50'):
            entry = entry_prices_cache['NIFTY_50']
            if len(nifty_prices) > 0:
                current = list(nifty_prices)[-1]
                diff = abs(current - entry)
                diff_percent = (diff / entry) * 100 if entry > 0 else 0
                tolerance = entry * 0.001  # 0.1%
                print(f"\n📏 NIFTY 50 distance from entry:")
                print(f"   Entry: ₹{entry:.2f}")
                print(f"   Current: ₹{current:.2f}")
                print(f"   Difference: ₹{diff:.2f} ({diff_percent:.3f}%)")
                print(f"   Tolerance: ₹{tolerance:.2f} (0.1%)")
                print(f"   Within tolerance: {'✅ YES' if diff <= tolerance else '❌ NO'}")
        
        if entry_prices_cache.get('NIFTY_BANK'):
            entry = entry_prices_cache['NIFTY_BANK']
            if len(bank_nifty_prices) > 0:
                current = list(bank_nifty_prices)[-1]
                diff = abs(current - entry)
                diff_percent = (diff / entry) * 100 if entry > 0 else 0
                tolerance = entry * 0.001  # 0.1%
                print(f"\n📏 NIFTY BANK distance from entry:")
                print(f"   Entry: ₹{entry:.2f}")
                print(f"   Current: ₹{current:.2f}")
                print(f"   Difference: ₹{diff:.2f} ({diff_percent:.3f}%)")
                print(f"   Tolerance: ₹{tolerance:.2f} (0.1%)")
                print(f"   Within tolerance: {'✅ YES' if diff <= tolerance else '❌ NO'}")
        
        return True
        
    except ImportError as e:
        print(f"\n⚠️  Could not import services module: {e}")
        print("   This is normal if the server is not running.")
        return False
    except Exception as e:
        print(f"\n❌ Error checking price data: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "=" * 80)
    print("TRADE EXECUTION DIAGNOSTIC")
    print("=" * 80)
    print("\nThis script checks why trades might not be executing.\n")
    
    # Check entry prices
    has_entry_prices = check_entry_prices()
    
    # Check price data (only if server is running)
    try:
        check_price_data()
    except:
        print("\n⚠️  Could not check runtime data. Make sure the server is running.")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    
    if not has_entry_prices:
        print("\n❌ MAIN ISSUE: Entry prices are not set!")
        print("\n   SOLUTION:")
        print("   1. Set entry prices using the API:")
        print("      curl -X POST http://localhost:5001/trading/set-entry-price \\")
        print("        -H 'Content-Type: application/json' \\")
        print("        -d '{\"instrument\": \"NIFTY_50\", \"entry_price\": 25000}'")
        print("\n   2. Or use the trading/get-trend endpoint to check current status")
    else:
        print("\n✅ Entry prices are set in database")
        print("\n   If trades still aren't executing, check:")
        print("   1. Is trend monitoring running? (should be started on server startup)")
        print("   2. Is price within 0.1% tolerance of entry level?")
        print("   3. Did price transition from above/below to 'at' level?")
        print("   4. Has an order already been placed? (check order_placed_at_level flag)")
        print("   5. Check server logs for error messages")
    
    print("\n" + "=" * 80 + "\n")

if __name__ == '__main__':
    main()


