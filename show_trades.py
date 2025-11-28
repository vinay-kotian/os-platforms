#!/usr/bin/env python3
"""
Script to display all captured trades from the database
"""
import sqlite3
import json
from datetime import datetime

DATABASE_FILE = 'app.db'

def format_trade(trade):
    """Format a trade dictionary for display"""
    formatted = {}
    for key, value in trade.items():
        if key in ['entry_time', 'exit_time', 'created_at', 'updated_at']:
            if value:
                try:
                    dt = datetime.fromisoformat(value)
                    formatted[key] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted[key] = value
            else:
                formatted[key] = value
        elif key in ['entry_price', 'exit_price', 'underlying_entry_price', 
                     'target_price', 'stoploss_price', 'profit_loss', 'profit_loss_percent']:
            formatted[key] = f"{value:.2f}" if value is not None else "N/A"
        else:
            formatted[key] = value
    return formatted

def show_trades():
    """Display all trades from database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get all trades
        cursor.execute('SELECT * FROM trades ORDER BY entry_time DESC')
        columns = [desc[0] for desc in cursor.description]
        trades = []
        for row in cursor.fetchall():
            trade_dict = dict(zip(columns, row))
            trades.append(trade_dict)
        
        # Get all paper trades
        cursor.execute('SELECT * FROM paper_trades ORDER BY entry_time DESC')
        columns = [desc[0] for desc in cursor.description]
        paper_trades = []
        for row in cursor.fetchall():
            trade_dict = dict(zip(columns, row))
            paper_trades.append(trade_dict)
        
        conn.close()
        
        print("=" * 80)
        print("CAPTURED TRADES")
        print("=" * 80)
        print(f"\n📊 Live Trades: {len(trades)}")
        print(f"📝 Paper Trades: {len(paper_trades)}")
        print()
        
        if trades:
            print("\n" + "=" * 80)
            print("LIVE TRADES")
            print("=" * 80)
            for i, trade in enumerate(trades, 1):
                print(f"\n{i}. Trade UUID: {trade.get('trade_uuid', 'N/A')}")
                print(f"   Instrument: {trade.get('instrument', 'N/A')}")
                print(f"   Option Type: {trade.get('option_type', 'N/A')}")
                print(f"   Symbol: {trade.get('tradingsymbol', 'N/A')}")
                print(f"   Quantity: {trade.get('quantity', 'N/A')}")
                print(f"   Entry Price: ₹{trade.get('entry_price', 0):.2f}")
                print(f"   Entry Time: {trade.get('entry_time', 'N/A')}")
                print(f"   Target: ₹{trade.get('target_price', 0):.2f} | Stop Loss: ₹{trade.get('stoploss_price', 0):.2f}")
                if trade.get('exit_price'):
                    print(f"   Exit Price: ₹{trade.get('exit_price', 0):.2f}")
                    print(f"   Exit Time: {trade.get('exit_time', 'N/A')}")
                    print(f"   Exit Reason: {trade.get('exit_reason', 'N/A')}")
                    print(f"   P&L: ₹{trade.get('profit_loss', 0):.2f} ({trade.get('profit_loss_percent', 0):.2f}%)")
                print(f"   Status: {trade.get('status', 'N/A')}")
                print("-" * 80)
        else:
            print("\nNo live trades found.")
        
        if paper_trades:
            print("\n" + "=" * 80)
            print("PAPER TRADES")
            print("=" * 80)
            for i, trade in enumerate(paper_trades, 1):
                print(f"\n{i}. Trade UUID: {trade.get('trade_uuid', 'N/A')}")
                print(f"   Instrument: {trade.get('instrument', 'N/A')}")
                print(f"   Option Type: {trade.get('option_type', 'N/A')}")
                print(f"   Symbol: {trade.get('tradingsymbol', 'N/A')}")
                print(f"   Quantity: {trade.get('quantity', 'N/A')}")
                print(f"   Entry Price: ₹{trade.get('entry_price', 0):.2f}")
                print(f"   Entry Time: {trade.get('entry_time', 'N/A')}")
                print(f"   Current Price: ₹{trade.get('current_price', 0):.2f}" if trade.get('current_price') else "   Current Price: N/A")
                print(f"   Target: ₹{trade.get('target_price', 0):.2f} | Stop Loss: ₹{trade.get('stoploss_price', 0):.2f}")
                if trade.get('exit_price'):
                    print(f"   Exit Price: ₹{trade.get('exit_price', 0):.2f}")
                    print(f"   Exit Time: {trade.get('exit_time', 'N/A')}")
                    print(f"   Exit Reason: {trade.get('exit_reason', 'N/A')}")
                    print(f"   P&L: ₹{trade.get('profit_loss', 0):.2f} ({trade.get('profit_loss_percent', 0):.2f}%)")
                print(f"   Status: {trade.get('status', 'N/A')}")
                print("-" * 80)
        else:
            print("\nNo paper trades found.")
        
        print("\n" + "=" * 80)
        
        # Summary
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
        open_paper = [t for t in paper_trades if t.get('status') == 'OPEN']
        closed_paper = [t for t in paper_trades if t.get('status') == 'CLOSED']
        
        print("\nSUMMARY:")
        print(f"  Live Trades - Open: {len(open_trades)}, Closed: {len(closed_trades)}")
        print(f"  Paper Trades - Open: {len(open_paper)}, Closed: {len(closed_paper)}")
        
        if closed_trades or closed_paper:
            total_pnl = sum(t.get('profit_loss', 0) or 0 for t in closed_trades + closed_paper)
            print(f"  Total P&L (Closed Trades): ₹{total_pnl:.2f}")
        
    except Exception as e:
        print(f"Error retrieving trades: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    show_trades()

