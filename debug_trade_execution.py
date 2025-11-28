#!/usr/bin/env python3
"""
Real-time diagnostic script to check why trades aren't executing
"""
import sys
import os
import time

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services import (
        entry_prices_cache,
        previous_price_position,
        order_placed_at_level,
        last_order_time,
        nifty_prices,
        bank_nifty_prices,
        trend_monitoring_running
    )
    
    print("=" * 80)
    print("REAL-TIME TRADE EXECUTION DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Check entry prices
    print("1. ENTRY PRICES:")
    nifty_entry = entry_prices_cache.get('NIFTY_50')
    bank_entry = entry_prices_cache.get('NIFTY_BANK')
    
    if nifty_entry:
        print(f"   ✅ NIFTY_50 entry price: ₹{nifty_entry:.2f}")
    else:
        print(f"   ❌ NIFTY_50 entry price: NOT SET")
        print(f"      → Set using: curl -X POST http://localhost:5001/trading/set-entry-price -H 'Content-Type: application/json' -d '{{\"instrument\": \"NIFTY_50\", \"entry_price\": <price>}}'")
    
    if bank_entry:
        print(f"   ✅ NIFTY_BANK entry price: ₹{bank_entry:.2f}")
    else:
        print(f"   ❌ NIFTY_BANK entry price: NOT SET")
        print(f"      → Set using: curl -X POST http://localhost:5001/trading/set-entry-price -H 'Content-Type: application/json' -d '{{\"instrument\": \"NIFTY_BANK\", \"entry_price\": <price>}}'")
    
    print()
    
    # Check price data
    print("2. PRICE DATA:")
    if len(nifty_prices) > 0:
        nifty_current = list(nifty_prices)[-1]
        print(f"   ✅ NIFTY_50: {len(nifty_prices)} prices collected, latest: ₹{nifty_current:.2f}")
        if nifty_entry:
            diff = abs(nifty_current - nifty_entry)
            diff_pct = (diff / nifty_entry) * 100 if nifty_entry > 0 else 0
            tolerance = nifty_entry * 0.001  # 0.1%
            print(f"      Distance from entry: ₹{diff:.2f} ({diff_pct:.3f}%)")
            print(f"      Tolerance (0.1%): ₹{tolerance:.2f}")
            print(f"      Within tolerance: {'✅ YES' if diff <= tolerance else '❌ NO'}")
    else:
        print(f"   ❌ NIFTY_50: No prices collected")
    
    if len(bank_nifty_prices) > 0:
        bank_current = list(bank_nifty_prices)[-1]
        print(f"   ✅ NIFTY_BANK: {len(bank_nifty_prices)} prices collected, latest: ₹{bank_current:.2f}")
        if bank_entry:
            diff = abs(bank_current - bank_entry)
            diff_pct = (diff / bank_entry) * 100 if bank_entry > 0 else 0
            tolerance = bank_entry * 0.001  # 0.1%
            print(f"      Distance from entry: ₹{diff:.2f} ({diff_pct:.3f}%)")
            print(f"      Tolerance (0.1%): ₹{tolerance:.2f}")
            print(f"      Within tolerance: {'✅ YES' if diff <= tolerance else '❌ NO'}")
    else:
        print(f"   ❌ NIFTY_BANK: No prices collected")
    
    print()
    
    # Check position tracking
    print("3. POSITION TRACKING:")
    nifty_pos = previous_price_position.get('NIFTY_50')
    bank_pos = previous_price_position.get('NIFTY_BANK')
    print(f"   NIFTY_50 previous position: {nifty_pos if nifty_pos else 'NOT INITIALIZED'}")
    print(f"   NIFTY_BANK previous position: {bank_pos if bank_pos else 'NOT INITIALIZED'}")
    print()
    
    # Check order flags
    print("4. ORDER STATUS:")
    nifty_order = order_placed_at_level.get('NIFTY_50', False)
    bank_order = order_placed_at_level.get('NIFTY_BANK', False)
    print(f"   NIFTY_50 order placed: {'✅ YES' if nifty_order else '❌ NO'}")
    print(f"   NIFTY_BANK order placed: {'✅ YES' if bank_order else '❌ NO'}")
    
    # Check last order time
    nifty_last = last_order_time.get('NIFTY_50')
    bank_last = last_order_time.get('NIFTY_BANK')
    if nifty_last:
        from datetime import datetime
        last_time = datetime.fromisoformat(nifty_last)
        elapsed = (datetime.now() - last_time).total_seconds()
        print(f"   NIFTY_50 last order: {elapsed:.1f} seconds ago")
    if bank_last:
        from datetime import datetime
        last_time = datetime.fromisoformat(bank_last)
        elapsed = (datetime.now() - last_time).total_seconds()
        print(f"   NIFTY_BANK last order: {elapsed:.1f} seconds ago")
    
    print()
    
    # Check monitoring status
    print("5. MONITORING STATUS:")
    print(f"   Trend monitoring running: {'✅ YES' if trend_monitoring_running else '❌ NO'}")
    print()
    
    # Summary
    print("=" * 80)
    print("DIAGNOSIS:")
    print("=" * 80)
    
    issues = []
    if not nifty_entry and not bank_entry:
        issues.append("❌ Entry prices are not set - this is REQUIRED for trade execution")
    if not trend_monitoring_running:
        issues.append("❌ Trend monitoring is not running")
    if len(nifty_prices) == 0 and len(bank_nifty_prices) == 0:
        issues.append("❌ No price data collected - WebSocket may not be working")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ All checks passed - trades should execute when price touches entry level")
        print()
        print("  If trades still don't execute, check:")
        print("    - Price must transition FROM above/below TO 'at' entry level")
        print("    - Price must be within 0.1% tolerance of entry level")
        print("    - No order should have been placed in last 60 seconds")
        print("    - Check server logs for detailed monitoring output")
    
    print()
    
except ImportError as e:
    print(f"❌ Could not import services module: {e}")
    print("   Make sure the Flask server is running")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


