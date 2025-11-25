"""
Supporting functions and services for the Flask application.
This module contains database operations, session management, alert processing,
and WebSocket handling functions.
"""

from typing import Any
import os
import json
import requests
import sqlite3
import uuid
from collections import deque
from datetime import datetime
from flask import session, has_request_context, request
from flask.json import jsonify
from flask_socketio import emit
from kiteconnect import KiteConnect, KiteTicker
import threading
import time
import numpy as np

# Import socketio from app (will be set by app.py)
socketio = None

# Constants
SESSION_FILE = 'session_data.json'
DATABASE_FILE = 'app.db'

# Global variables (shared with app.py)
user_api_key = None
user_api_secret = None
kite = None
price_history: deque[Any] = deque(maxlen=20)  # window of last 20 ticks

# Global dictionary to store WebSocket prices
websocket_prices = {
    'NIFTY 50': {'last_price': 0, 'timestamp': None, 'previous_close': 0},
    'NIFTY BANK': {'last_price': 0, 'timestamp': None, 'previous_close': 0}
}

# Global dictionary to store option prices from WebSocket (for paper trading)
# Key: tradingsymbol (e.g., "NIFTY26DEC23000CE"), Value: {'last_price': price, 'timestamp': timestamp}
option_websocket_prices = {}

# Mapping from instrument_token to tradingsymbol for options (for WebSocket price tracking)
# Key: instrument_token, Value: {'tradingsymbol': symbol, 'exchange': exchange}
option_token_to_symbol = {}

# Mapping from tradingsymbol to instrument_token for options
# Key: tradingsymbol, Value: instrument_token
option_symbol_to_token = {}

# Global WebSocket ticker instance
kws = None
continuous_websocket_running = False
continuous_websocket_thread = None
continuous_kws = None

# Dictionary to store previous prices for alert crossing detection
alert_previous_prices = {}

# Price deques for trend detection (separate for each instrument)
nifty_prices = deque(maxlen=20)  # Price history for NIFTY 50
bank_nifty_prices = deque(maxlen=20)  # Price history for NIFTY BANK

# Entry prices for trading logic (cached from database)
# Dictionary to cache entry prices: {'NIFTY_50': price, 'NIFTY_BANK': price}
entry_prices_cache = {
    'NIFTY_50': None,
    'NIFTY_BANK': None
}

# Previous trends for each instrument (to detect trend reversals)
# Dictionary to track previous trend: {'NIFTY_50': 'UPTREND', 'NIFTY_BANK': 'DOWNTREND', etc.}
previous_trends = {
    'NIFTY_50': None,
    'NIFTY_BANK': None
}

# Track if order was already placed at entry level (to avoid duplicate orders)
# Dictionary: {'NIFTY_50': True/False, 'NIFTY_BANK': True/False}
order_placed_at_level = {
    'NIFTY_50': False,
    'NIFTY_BANK': False
}

# Track previous price position relative to entry level (to detect approach direction)
# Dictionary: {'NIFTY_50': 'above'/'below'/'at', 'NIFTY_BANK': 'above'/'below'/'at'}
previous_price_position = {
    'NIFTY_50': None,
    'NIFTY_BANK': None
}

# Flag to control trend monitoring background thread
trend_monitoring_running = False
trend_monitoring_thread = None

# Feature flag for paper trading
PAPER_TRADING_ENABLED = True  # Set to False for live trading

# Flag to control paper trade monitoring background thread
paper_trade_monitoring_running = False
paper_trade_monitoring_thread = None


# ============================================================================
# Trend Detection Functions
# ============================================================================

def get_trend(prices_deque):
    """
    Calculate trend based on linear regression of price history.
    
    Args:
        prices_deque: deque containing price values (floats)
    
    Returns:
        str: "UPTREND", "DOWNTREND", "SIDEWAYS", or "NO_TREND"
    """
    if len(prices_deque) < 10:
        return "NO_TREND"
    
    # Convert deque to numpy array
    y = np.array(list(prices_deque))
    x = np.arange(len(prices_deque))
    
    # Calculate linear regression slope
    slope = np.polyfit(x, y, 1)[0]
    
    # Determine trend based on slope
    if slope > 0:
        return "UPTREND"
    elif slope < 0:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"


# ============================================================================
# Trading Entry Functions with Target and Stop Loss
# ============================================================================

def subscribe_option_to_websocket(tradingsymbol, exchange="NFO"):
    """
    Subscribe to an option instrument in the WebSocket for real-time price updates.
    
    Args:
        tradingsymbol: Option tradingsymbol (e.g., "NIFTY26DEC23000CE")
        exchange: Exchange (default: "NFO")
    
    Returns:
        bool: True if subscribed successfully, False otherwise
    """
    global continuous_kws, kite, option_symbol_to_token, option_token_to_symbol, option_websocket_prices
    
    if not continuous_kws or not continuous_websocket_running:
        print(f"⚠️  WebSocket not running - cannot subscribe to {tradingsymbol}")
        return False
    
    if not kite:
        print(f"⚠️  KiteConnect not initialized - cannot subscribe to {tradingsymbol}")
        return False
    
    try:
        # Check if already subscribed
        if tradingsymbol in option_symbol_to_token:
            print(f"Already subscribed to {tradingsymbol}")
            return True
        
        # Get instrument token for the option
        instruments = kite.instruments(exchange)
        option_instrument = next(
            (inst for inst in instruments if inst.get('tradingsymbol') == tradingsymbol),
            None
        )
        
        if not option_instrument:
            print(f"⚠️  Option {tradingsymbol} not found in instruments")
            return False
        
        option_token = option_instrument['instrument_token']
        
        # Store mappings
        option_symbol_to_token[tradingsymbol] = option_token
        option_token_to_symbol[option_token] = {
            'tradingsymbol': tradingsymbol,
            'exchange': exchange
        }
        
        # Initialize price in option_websocket_prices
        option_key = f"{exchange}:{tradingsymbol}"
        option_websocket_prices[option_key] = {
            'last_price': 0,
            'timestamp': None
        }
        
        # Subscribe to the option in WebSocket
        continuous_kws.subscribe([option_token])
        continuous_kws.set_mode(continuous_kws.MODE_LTP, [option_token])
        
        print(f"✅ Subscribed to option {tradingsymbol} (token: {option_token}) for WebSocket price tracking")
        return True
        
    except Exception as e:
        print(f"Error subscribing option {tradingsymbol} to WebSocket: {e}")
        return False


def save_paper_trade_entry(instrument, option_type, tradingsymbol, exchange, quantity, 
                           entry_price, underlying_entry_price, target_price, stoploss_price,
                           user_id='default_user'):
    """
    Save paper trade entry to database (for paper trading mode).
    
    Args:
        instrument: "NIFTY 50" or "NIFTY BANK"
        option_type: "CALL" or "PUT"
        tradingsymbol: Option tradingsymbol
        exchange: Exchange (e.g., "NFO")
        quantity: Quantity
        entry_price: Option premium at entry
        underlying_entry_price: Underlying price at entry
        target_price: Target price (15% profit)
        stoploss_price: Stop loss price (5% loss)
        user_id: User ID
    
    Returns:
        str: Trade UUID or None if failed
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        trade_uuid = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        
        # Map instrument names
        instrument_map = {
            "NIFTY 50": "NIFTY_50",
            "NIFTY BANK": "NIFTY_BANK"
        }
        instrument_db = instrument_map.get(instrument, instrument)
        
        cursor.execute('''
            INSERT INTO paper_trades 
            (trade_uuid, user_id, instrument, option_type, tradingsymbol, exchange, quantity,
             entry_price, entry_time, underlying_entry_price, target_price, stoploss_price,
             current_price, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        ''', (trade_uuid, user_id, instrument_db, option_type, tradingsymbol, exchange, quantity,
              entry_price, current_time, underlying_entry_price, target_price, stoploss_price,
              entry_price, current_time, current_time))
        
        conn.commit()
        conn.close()
        
        # Subscribe to option in WebSocket for real-time price updates
        subscribe_option_to_websocket(tradingsymbol, exchange)
        
        print(f"📝 Paper trade entry saved: {trade_uuid}")
        return trade_uuid
        
    except Exception as e:
        print(f"Error saving paper trade entry to database: {e}")
        return None


def save_trade_entry(instrument, option_type, tradingsymbol, exchange, quantity, 
                     entry_price, underlying_entry_price, target_price, stoploss_price,
                     order_id, target_gtt_id, stoploss_gtt_id, user_id='default_user'):
    """
    Save trade entry to database.
    
    Args:
        instrument: "NIFTY 50" or "NIFTY BANK"
        option_type: "CALL" or "PUT"
        tradingsymbol: Option tradingsymbol
        exchange: Exchange (e.g., "NFO")
        quantity: Quantity
        entry_price: Option premium at entry
        underlying_entry_price: Underlying price at entry
        target_price: Target price (15% profit)
        stoploss_price: Stop loss price (5% loss)
        order_id: Order ID from Kite
        target_gtt_id: Target GTT ID
        stoploss_gtt_id: Stop loss GTT ID
        user_id: User ID
    
    Returns:
        str: Trade UUID or None if failed
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        trade_uuid = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        
        # Map instrument names
        instrument_map = {
            "NIFTY 50": "NIFTY_50",
            "NIFTY BANK": "NIFTY_BANK"
        }
        instrument_db = instrument_map.get(instrument, instrument)
        
        cursor.execute('''
            INSERT INTO trades 
            (trade_uuid, user_id, instrument, option_type, tradingsymbol, exchange, quantity,
             entry_price, entry_time, underlying_entry_price, target_price, stoploss_price,
             order_id, target_gtt_id, stoploss_gtt_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        ''', (trade_uuid, user_id, instrument_db, option_type, tradingsymbol, exchange, quantity,
              entry_price, current_time, underlying_entry_price, target_price, stoploss_price,
              order_id, target_gtt_id, stoploss_gtt_id, current_time, current_time))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Trade entry saved to database: {trade_uuid}")
        return trade_uuid
        
    except Exception as e:
        print(f"Error saving trade entry to database: {e}")
        return None


def update_trade_exit(trade_uuid, exit_price, exit_reason, user_id='default_user'):
    """
    Update trade exit information when trade is closed.
    
    Args:
        trade_uuid: Trade UUID
        exit_price: Option premium at exit
        exit_reason: 'TARGET', 'STOPLOSS', or 'MANUAL'
        user_id: User ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get trade entry details
        cursor.execute('''
            SELECT entry_price, quantity FROM trades 
            WHERE trade_uuid = ? AND user_id = ? AND status = 'OPEN'
        ''', (trade_uuid, user_id))
        
        trade = cursor.fetchone()
        if not trade:
            print(f"Trade {trade_uuid} not found or already closed")
            conn.close()
            return False
        
        entry_price, quantity = trade
        
        # Calculate profit/loss
        profit_loss = (exit_price - entry_price) * quantity
        profit_loss_percent = ((exit_price - entry_price) / entry_price) * 100
        
        current_time = datetime.now().isoformat()
        
        # Update trade
        cursor.execute('''
            UPDATE trades 
            SET exit_price = ?, exit_time = ?, exit_reason = ?,
                profit_loss = ?, profit_loss_percent = ?, status = 'CLOSED', updated_at = ?
            WHERE trade_uuid = ? AND user_id = ?
        ''', (exit_price, current_time, exit_reason, profit_loss, profit_loss_percent, 
              current_time, trade_uuid, user_id))
        
        conn.commit()
        conn.close()
        
        result = "PROFIT" if profit_loss > 0 else "LOSS"
        print(f"✅ Trade exit updated: {trade_uuid} - {result} of {abs(profit_loss):.2f} ({profit_loss_percent:.2f}%)")
        return True
        
    except Exception as e:
        print(f"Error updating trade exit: {e}")
        return False


def get_trades(user_id='default_user', status=None, instrument=None):
    """
    Get trades from database.
    
    Args:
        user_id: User ID
        status: Filter by status ('OPEN', 'CLOSED') or None for all
        instrument: Filter by instrument ('NIFTY_50', 'NIFTY_BANK') or None for all
    
    Returns:
        list: List of trade dictionaries
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM trades WHERE user_id = ?'
        params = [user_id]
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        if instrument:
            query += ' AND instrument = ?'
            params.append(instrument)
        
        query += ' ORDER BY entry_time DESC'
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        trades = []
        
        for row in cursor.fetchall():
            trade_dict = dict(zip(columns, row))
            trades.append(trade_dict)
        
        conn.close()
        return trades
        
    except Exception as e:
        print(f"Error getting trades: {e}")
        return []


def check_and_update_trades_from_orders(kite, user_id='default_user'):
    """
    Check open trades and update them if orders have been executed (GTT triggered).
    This should be called periodically to sync trade status with actual order execution.
    
    Args:
        kite: KiteConnect instance
        user_id: User ID
    
    Returns:
        int: Number of trades updated
    """
    if not kite:
        return 0
    
    try:
        # Get all open trades
        open_trades = get_trades(user_id=user_id, status='OPEN')
        if not open_trades:
            return 0
        
        updated_count = 0
        
        # Get recent orders
        try:
            orders = kite.orders()
        except:
            return 0
        
        for trade in open_trades:
            trade_uuid = trade['trade_uuid']
            target_gtt_id = trade.get('target_gtt_id')
            stoploss_gtt_id = trade.get('stoploss_gtt_id')
            tradingsymbol = trade['tradingsymbol']
            
            # Check if any exit order was placed (GTT triggered)
            # Look for SELL orders for this tradingsymbol
            exit_orders = [
                o for o in orders
                if o.get('tradingsymbol') == tradingsymbol
                and o.get('transaction_type') == 'SELL'
                and o.get('status') == 'COMPLETE'
                and o.get('order_timestamp', '') >= trade['entry_time']
            ]
            
            if exit_orders:
                # Get the most recent exit order
                latest_exit = max(exit_orders, key=lambda x: x.get('order_timestamp', ''))
                exit_price = latest_exit.get('average_price') or latest_exit.get('price', 0)
                
                # Determine exit reason based on price
                target_price = trade['target_price']
                stoploss_price = trade['stoploss_price']
                
                if abs(exit_price - target_price) < abs(exit_price - stoploss_price):
                    exit_reason = 'TARGET'
                else:
                    exit_reason = 'STOPLOSS'
                
                # Update trade
                if update_trade_exit(trade_uuid, exit_price, exit_reason, user_id):
                    updated_count += 1
        
        return updated_count
        
    except Exception as e:
        print(f"Error checking and updating trades: {e}")
        return 0


def place_option_with_tp_sl(kite, exchange, tradingsymbol, quantity, transaction_type,
                            price=None, product="MIS", order_type="MARKET",
                            target_price=None, stoploss_trigger=None, stoploss_price=None,
                            instrument=None, option_type=None, underlying_entry_price=None):
    """
    Place an option order with target price (15% profit) and stop loss (5%).
    Uses GTT (Good Till Triggered) for automatic target and stop loss execution.
    
    Args:
        kite: KiteConnect instance
        exchange: Exchange (e.g., "NFO")
        tradingsymbol: Trading symbol (e.g., "NIFTY26DEC23000CE")
        quantity: Quantity (lot size)
        transaction_type: kite.TRANSACTION_TYPE_BUY or SELL
        price: Limit price or None for market
        product: "MIS" or "NRML"
        order_type: "MARKET" or "LIMIT"
        target_price: Target limit price for 15% profit
        stoploss_trigger: Trigger price for stop loss
        stoploss_price: Limit price for stop loss order
        instrument: Instrument name (for database tracking)
        option_type: "CALL" or "PUT" (for database tracking)
        underlying_entry_price: Underlying price at entry (for database tracking)
    
    Returns:
        dict: {"order_id": order_id, "gtt_ids": [gtt_ids], "trade_uuid": trade_uuid}
    """
    order_id = None
    gtt_ids = []
    target_gtt_id = None
    stoploss_gtt_id = None
    entry_price = None
    
    # 1) Place main order
    try:
        order_id = kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=getattr(kite, f"ORDER_TYPE_{order_type}"),
            product=getattr(kite, f"PRODUCT_{product}"),
            price=price
        )
        print(f"Main order placed, order_id: {order_id}")
    except Exception as e:
        print(f"Placing main order failed: {e}")
        raise
    
    # 2) Wait & check order execution before placing GTTs
    for _ in range(30):  # try for ~30 seconds
        try:
            orders = kite.orders()
            my_order = next((o for o in orders if o.get("order_id") == order_id), None)
            if my_order and my_order.get("status") in ("COMPLETE", "OPEN", "TRIGGER PENDING"):
                print(f"Order status: {my_order.get('status')}")
                break
            time.sleep(1)
        except Exception as e:
            print(f"Error checking order status: {e}")
            break
    else:
        print("Could not confirm order fill quickly; proceeding with GTT setup anyway.")
    
    # 3) Place GTT for target (15% profit)
    if target_price is not None:
        try:
            target_payload = {
                "type": "single",
                "condition": {
                    "exchange": exchange,
                    "tradingsymbol": tradingsymbol,
                    "trigger_values": [target_price],
                    "last_price": None
                },
                "orders": [{
                    "exchange": exchange,
                    "tradingsymbol": tradingsymbol,
                    "transaction_type": kite.TRANSACTION_TYPE_SELL if transaction_type == kite.TRANSACTION_TYPE_BUY else kite.TRANSACTION_TYPE_BUY,
                    "quantity": quantity,
                    "product": product,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "price": target_price
                }]
            }
            gtt_resp = kite.place_gtt(**target_payload)
            # GTT response may have "trigger_id" or "id" depending on API version
            gtt_id = gtt_resp.get("trigger_id") or gtt_resp.get("id")
            if gtt_id:
                gtt_ids.append(gtt_id)
                target_gtt_id = gtt_id
            print(f"Target GTT placed (15% profit): {gtt_resp}")
        except Exception as e:
            print(f"Failed to place target GTT: {e}")
    
    # 4) Place GTT for stop loss (5%)
    if stoploss_trigger is not None and stoploss_price is not None:
        try:
            sl_payload = {
                "type": "single",
                "condition": {
                    "exchange": exchange,
                    "tradingsymbol": tradingsymbol,
                    "trigger_values": [stoploss_trigger],
                    "last_price": None
                },
                "orders": [{
                    "exchange": exchange,
                    "tradingsymbol": tradingsymbol,
                    "transaction_type": kite.TRANSACTION_TYPE_SELL if transaction_type == kite.TRANSACTION_TYPE_BUY else kite.TRANSACTION_TYPE_BUY,
                    "quantity": quantity,
                    "product": product,
                    "order_type": kite.ORDER_TYPE_LIMIT,
                    "price": stoploss_price
                }]
            }
            gtt_resp = kite.place_gtt(**sl_payload)
            # GTT response may have "trigger_id" or "id" depending on API version
            gtt_id = gtt_resp.get("trigger_id") or gtt_resp.get("id")
            if gtt_id:
                gtt_ids.append(gtt_id)
                stoploss_gtt_id = gtt_id
            print(f"Stoploss GTT placed (5%): {gtt_resp}")
        except Exception as e:
            print(f"Failed to place stoploss GTT: {e}")
    
    # Save trade entry to database
    trade_uuid = None
    if instrument and option_type and underlying_entry_price and entry_price:
        trade_uuid = save_trade_entry(
            instrument=instrument,
            option_type=option_type,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            quantity=quantity,
            entry_price=entry_price,
            underlying_entry_price=underlying_entry_price,
            target_price=target_price if target_price else 0,
            stoploss_price=stoploss_price if stoploss_price else 0,
            order_id=str(order_id) if order_id else None,
            target_gtt_id=str(target_gtt_id) if target_gtt_id else None,
            stoploss_gtt_id=str(stoploss_gtt_id) if stoploss_gtt_id else None
        )
    
    return {
        "order_id": order_id,
        "gtt_ids": gtt_ids,
        "trade_uuid": trade_uuid,
        "entry_price": entry_price
    }


def get_option_tradingsymbol(kite, instrument, entry_price, option_type="CE"):
    """
    Get the ATM (At The Money) option tradingsymbol based on entry price.
    
    Args:
        kite: KiteConnect instance
        instrument: "NIFTY 50" or "NIFTY BANK"
        entry_price: Entry price (underlying price) to find ATM strike
        option_type: "CE" for CALL, "PE" for PUT
    
    Returns:
        str: Tradingsymbol (e.g., "NIFTY26DEC23000CE") or None if not found
    """
    if not kite:
        print("KiteConnect not initialized")
        return None
    
    try:
        # Map instrument names to underlying symbols
        underlying_map = {
            "NIFTY 50": "NIFTY",
            "NIFTY BANK": "BANKNIFTY"
        }
        
        underlying = underlying_map.get(instrument)
        if not underlying:
            print(f"Unknown instrument: {instrument}")
            return None
        
        # Get strike interval (50 for NIFTY, 100 for BANKNIFTY)
        strike_interval = 50 if instrument == "NIFTY 50" else 100
        
        # Calculate ATM strike (round to nearest strike interval)
        atm_strike = round(entry_price / strike_interval) * strike_interval
        
        # Get all NFO instruments
        instruments = kite.instruments("NFO")
        
        # Filter for the underlying and option type
        filtered = [
            inst for inst in instruments
            if inst["name"] == underlying
            and inst["instrument_type"] == option_type
            and inst["strike"] == atm_strike
        ]
        
        if not filtered:
            print(f"No {option_type} options found for {underlying} at strike {atm_strike}")
            return None
        
        # Get the nearest expiry (sort by expiry date, take the first)
        filtered.sort(key=lambda x: x["expiry"])
        nearest_option = filtered[0]
        
        tradingsymbol = nearest_option["tradingsymbol"]
        print(f"Found ATM {option_type} option: {tradingsymbol} (Strike: {atm_strike}, Expiry: {nearest_option['expiry']})")
        
        return tradingsymbol
        
    except Exception as e:
        print(f"Error getting option tradingsymbol: {e}")
        return None


def place_call_order(price, instrument="NIFTY 50"):
    """
    Place a CALL order with 15% profit target and 5% stop loss.
    Gets ATM (At The Money) option based on entry price.
    
    Args:
        price: Entry price (underlying spot price) - used to find ATM strike
        instrument: Instrument name (NIFTY 50 or NIFTY BANK)
    """
    global kite
    
    if not kite:
        print(f"❌ CALL ORDER: KiteConnect not initialized for {instrument}")
        return
    
    try:
        # Configuration - these should be set based on your requirements
        exchange = "NFO"
        quantity = 50  # Lot size (adjust based on your requirements)
        product = "MIS"  # or "NRML"
        order_type = "MARKET"
        
        # Get tradingsymbol for ATM CALL option based on entry price
        tradingsymbol = get_option_tradingsymbol(kite, instrument, price, option_type="CE")
        if not tradingsymbol:
            print(f"❌ CALL ORDER: Could not determine tradingsymbol for {instrument} at entry price {price}")
            return
        
        # Fetch current option premium from market
        try:
            option_quote = kite.quote(f"{exchange}:{tradingsymbol}")
            option_data = option_quote.get(f"{exchange}:{tradingsymbol}", {})
            option_premium = option_data.get("last_price", 0)
            
            if option_premium == 0:
                # Try to get LTP from depth or use a fallback
                option_premium = option_data.get("depth", [{}])[0].get("price", 0) if option_data.get("depth") else 0
                
            if option_premium == 0:
                print(f"⚠️  CALL ORDER: Could not fetch option premium for {tradingsymbol}")
                print(f"   Placing order without GTT - please set target and stop loss manually")
                # Place order without GTT as fallback
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=tradingsymbol,
                    transaction_type=kite.TRANSACTION_TYPE_BUY,
                    quantity=quantity,
                    order_type=kite.ORDER_TYPE_MARKET,
                    product=kite.PRODUCT_MIS
                )
                print(f"🔼 CALL ORDER PLACED for {instrument} at {price} (order_id: {order_id})")
                print(f"   Tradingsymbol: {tradingsymbol}")
                return
                
        except Exception as e:
            print(f"⚠️  CALL ORDER: Error fetching option premium: {e}")
            print(f"   Placing order without GTT")
            # Place order without GTT as fallback
            order_id = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                order_type=kite.ORDER_TYPE_MARKET,
                product=kite.PRODUCT_MIS
            )
            print(f"🔼 CALL ORDER PLACED for {instrument} at {price} (order_id: {order_id})")
            return
        
        # Calculate 15% profit target and 5% stop loss based on option premium
        target_price = round(option_premium * 1.15, 2)  # 15% profit
        stoploss_trigger = round(option_premium * 0.95, 2)  # 5% stop loss trigger
        stoploss_price = round(option_premium * 0.94, 2)  # Slightly below trigger for execution
        
        print(f"📊 Option Premium: {option_premium:.2f}")
        print(f"   Target (15%): {target_price:.2f}")
        print(f"   Stop Loss (5%): {stoploss_price:.2f}")
        
        # Place order with target and stop loss
        result = place_option_with_tp_sl(
            kite=kite,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            quantity=quantity,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            order_type=order_type,
            product=product,
            target_price=target_price,
            stoploss_trigger=stoploss_trigger,
            stoploss_price=stoploss_price
        )
        
        print(f"🔼 CALL ORDER PLACED for {instrument} at entry price {price}")
        print(f"   Tradingsymbol: {tradingsymbol}")
        print(f"   Order ID: {result['order_id']}")
        print(f"   Target (15%): {target_price:.2f}")
        print(f"   Stop Loss (5%): {stoploss_price:.2f}")
        print(f"   GTT IDs: {result['gtt_ids']}")
        
    except Exception as e:
        print(f"❌ Error placing CALL order for {instrument}: {e}")
        import traceback
        traceback.print_exc()


def place_put_order(price, instrument="NIFTY 50"):
    """
    Place a PUT order with 15% profit target and 5% stop loss.
    Gets ATM (At The Money) option based on entry price.
    
    Args:
        price: Entry price (underlying spot price) - used to find ATM strike
        instrument: Instrument name (NIFTY 50 or NIFTY BANK)
    """
    global kite
    
    if not kite:
        print(f"❌ PUT ORDER: KiteConnect not initialized for {instrument}")
        return
    
    try:
        # Configuration - these should be set based on your requirements
        exchange = "NFO"
        quantity = 50  # Lot size (adjust based on your requirements)
        product = "MIS"  # or "NRML"
        order_type = "MARKET"
        
        # Get tradingsymbol for ATM PUT option based on entry price
        tradingsymbol = get_option_tradingsymbol(kite, instrument, price, option_type="PE")
        if not tradingsymbol:
            print(f"❌ PUT ORDER: Could not determine tradingsymbol for {instrument} at entry price {price}")
            return
        
        # Fetch current option premium from market
        try:
            option_quote = kite.quote(f"{exchange}:{tradingsymbol}")
            option_data = option_quote.get(f"{exchange}:{tradingsymbol}", {})
            option_premium = option_data.get("last_price", 0)
            
            if option_premium == 0:
                # Try to get LTP from depth or use a fallback
                option_premium = option_data.get("depth", [{}])[0].get("price", 0) if option_data.get("depth") else 0
                
            if option_premium == 0:
                print(f"⚠️  PUT ORDER: Could not fetch option premium for {tradingsymbol}")
                print(f"   Placing order without GTT - please set target and stop loss manually")
                # Place order without GTT as fallback
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=tradingsymbol,
                    transaction_type=kite.TRANSACTION_TYPE_BUY,
                    quantity=quantity,
                    order_type=kite.ORDER_TYPE_MARKET,
                    product=kite.PRODUCT_MIS
                )
                print(f"🔽 PUT ORDER PLACED for {instrument} at {price} (order_id: {order_id})")
                print(f"   Tradingsymbol: {tradingsymbol}")
                return
                
        except Exception as e:
            print(f"⚠️  PUT ORDER: Error fetching option premium: {e}")
            print(f"   Placing order without GTT")
            # Place order without GTT as fallback
            order_id = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                order_type=kite.ORDER_TYPE_MARKET,
                product=kite.PRODUCT_MIS
            )
            print(f"🔽 PUT ORDER PLACED for {instrument} at {price} (order_id: {order_id})")
            return
        
        # Calculate 15% profit target and 5% stop loss based on option premium
        target_price = round(option_premium * 1.15, 2)  # 15% profit
        stoploss_trigger = round(option_premium * 0.95, 2)  # 5% stop loss trigger
        stoploss_price = round(option_premium * 0.94, 2)  # Slightly below trigger for execution
        
        print(f"📊 Option Premium: {option_premium:.2f}")
        print(f"   Target (15%): {target_price:.2f}")
        print(f"   Stop Loss (5%): {stoploss_price:.2f}")
        
        # Check if paper trading is enabled
        if PAPER_TRADING_ENABLED:
            # Paper trading: Save to paper_trades table without placing real order
            trade_uuid = save_paper_trade_entry(
                instrument=instrument,
                option_type="PUT",
                tradingsymbol=tradingsymbol,
                exchange=exchange,
                quantity=quantity,
                entry_price=option_premium,
                underlying_entry_price=price,
                target_price=target_price,
                stoploss_price=stoploss_price
            )
            
            print(f"📝 PAPER TRADE - PUT ORDER for {instrument} at entry price {price}")
            print(f"   Tradingsymbol: {tradingsymbol}")
            print(f"   Entry Premium: {option_premium:.2f}")
            print(f"   Target (15%): {target_price:.2f}")
            print(f"   Stop Loss (5%): {stoploss_price:.2f}")
            print(f"   Trade UUID: {trade_uuid}")
        else:
            # Live trading: Place actual order
            result = place_option_with_tp_sl(
                kite=kite,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                quantity=quantity,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                order_type=order_type,
                product=product,
                target_price=target_price,
                stoploss_trigger=stoploss_trigger,
                stoploss_price=stoploss_price,
                instrument=instrument,
                option_type="PUT",
                underlying_entry_price=price
            )
            
            print(f"🔽 LIVE TRADE - PUT ORDER PLACED for {instrument} at entry price {price}")
            print(f"   Tradingsymbol: {tradingsymbol}")
            print(f"   Order ID: {result['order_id']}")
            print(f"   Entry Premium: {result.get('entry_price', option_premium):.2f}")
            print(f"   Target (15%): {target_price:.2f}")
            print(f"   Stop Loss (5%): {stoploss_price:.2f}")
            print(f"   Trade UUID: {result.get('trade_uuid', 'N/A')}")
            print(f"   GTT IDs: {result['gtt_ids']}")
        
    except Exception as e:
        print(f"❌ Error placing PUT order for {instrument}: {e}")
        import traceback
        traceback.print_exc()


def check_trend_reversal(instrument_name, cache_key, prices_deque):
    """
    Check if price touches entry level and place reversal order based on approach direction.
    This function is called by the background monitoring thread.
    
    Trading Logic (Reversal Strategy):
    - If price comes from UP (above level) and touches the level → Buy CALL (expecting reversal up)
    - If price comes from DOWN (below level) and touches the level → Buy PUT (expecting reversal down)
    
    Args:
        instrument_name: Display name ("NIFTY 50" or "NIFTY BANK")
        cache_key: Cache key ("NIFTY_50" or "NIFTY_BANK")
        prices_deque: The price deque for this instrument
    """
    global previous_trends, entry_prices_cache, order_placed_at_level, previous_price_position
    
    # Skip if deque is empty
    if len(prices_deque) == 0:
        return
    
    # Get entry price for this instrument from cache
    entry_price = entry_prices_cache.get(cache_key)
    
    # Skip if entry price is not set
    if entry_price is None:
        return
    
    # Get current price (last price in deque)
    current_price = list(prices_deque)[-1]
    
    # Check if price is at/near entry level (within 0.1% tolerance)
    price_tolerance = entry_price * 0.001  # 0.1% of entry price
    price_diff = abs(current_price - entry_price)
    is_at_entry_level = price_diff <= price_tolerance
    
    # Determine current price position relative to entry level
    if is_at_entry_level:
        current_position = 'at'
    elif current_price > entry_price:
        current_position = 'above'
    else:
        current_position = 'below'
    
    # Get previous price position
    previous_position = previous_price_position.get(cache_key)
    
    # Check if price just touched the level (transitioned from above/below to at level)
    if is_at_entry_level and previous_position is not None and previous_position != 'at':
        # Price just touched the level from a different position
        
        # Only place order if we haven't already placed one at this level
        if not order_placed_at_level.get(cache_key, False):
            # Price came from UP (above) and touched level → Buy CALL (reversal up expected)
            if previous_position == 'above':
                place_call_order(current_price, instrument_name)
                order_placed_at_level[cache_key] = True
                print(f"🔼 CALL ORDER: {instrument_name} price touched entry level {entry_price} from UP (reversal trade) - current: {current_price}")
            
            # Price came from DOWN (below) and touched level → Buy PUT (reversal down expected)
            elif previous_position == 'below':
                place_put_order(current_price, instrument_name)
                order_placed_at_level[cache_key] = True
                print(f"🔽 PUT ORDER: {instrument_name} price touched entry level {entry_price} from DOWN (reversal trade) - current: {current_price}")
    
    # Reset order flag when price moves away from entry level
    if not is_at_entry_level:
        order_placed_at_level[cache_key] = False
    
    # Update previous price position for next comparison
    previous_price_position[cache_key] = current_position
    
    # Also update previous trend (for reference/debugging)
    current_trend = get_trend(prices_deque)
    if current_trend != "NO_TREND":
        previous_trends[cache_key] = current_trend


def on_tick(price, instrument="NIFTY 50", entry_price=None):
    """
    Process a new price tick - appends price to deque.
    Trend reversal checking is handled by the background monitoring thread.
    
    Args:
        price: Current price
        instrument: Instrument name ("NIFTY 50" or "NIFTY BANK")
        entry_price: Entry price threshold (optional, not used for trend reversal strategy)
    """
    global nifty_prices, bank_nifty_prices
    
    # Select the appropriate price deque
    if instrument == "NIFTY 50":
        prices_deque = nifty_prices
    elif instrument == "NIFTY BANK":
        prices_deque = bank_nifty_prices
    else:
        print(f"Unknown instrument: {instrument}")
        return
    
    # Append price to deque (trend reversal checking happens in background thread)
    prices_deque.append(price)


# ============================================================================
# Database Functions
# ============================================================================

def init_database():
    """Initialize the SQLite database and create tables"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                lhs_exchange TEXT NOT NULL,
                lhs_tradingsymbol TEXT NOT NULL,
                lhs_attribute TEXT NOT NULL,
                operator TEXT NOT NULL,
                rhs_type TEXT NOT NULL,
                rhs_constant REAL,
                rhs_exchange TEXT,
                rhs_tradingsymbol TEXT,
                rhs_attribute TEXT,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                alert_count INTEGER DEFAULT 0,
                disabled_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                kite_response TEXT NOT NULL,
                last_triggered_at TEXT,
                last_triggered_price REAL
            )
        ''')
        
        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE alerts ADD COLUMN last_triggered_at TEXT')
        except:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE alerts ADD COLUMN last_triggered_price REAL')
        except:
            pass  # Column already exists
        
        # Create level table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS level (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                index_type TEXT NOT NULL,  -- 'BANK_NIFTY' or 'NIFTY_50'
                level_value REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                created_date TEXT NOT NULL  -- Date when level was created (for daily refresh)
            )
        ''')
        
        # Create entry_prices table for trading entry prices
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                instrument TEXT NOT NULL UNIQUE,  -- 'NIFTY_50' or 'NIFTY_BANK'
                entry_price REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create trades table for tracking all live trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_uuid TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                instrument TEXT NOT NULL,  -- 'NIFTY_50' or 'NIFTY_BANK'
                option_type TEXT NOT NULL,  -- 'CALL' or 'PUT'
                tradingsymbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,  -- Option premium at entry
                entry_time TEXT NOT NULL,
                underlying_entry_price REAL NOT NULL,  -- Underlying price when entered
                target_price REAL NOT NULL,  -- 15% profit target
                stoploss_price REAL NOT NULL,  -- 5% stop loss
                order_id TEXT,
                target_gtt_id TEXT,
                stoploss_gtt_id TEXT,
                exit_price REAL,  -- Option premium at exit
                exit_time TEXT,
                exit_reason TEXT,  -- 'TARGET', 'STOPLOSS', 'MANUAL'
                profit_loss REAL,  -- Profit/Loss amount
                profit_loss_percent REAL,  -- Profit/Loss percentage
                status TEXT NOT NULL DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED'
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create paper_trades table for paper trading
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_uuid TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                instrument TEXT NOT NULL,  -- 'NIFTY_50' or 'NIFTY_BANK'
                option_type TEXT NOT NULL,  -- 'CALL' or 'PUT'
                tradingsymbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                entry_price REAL NOT NULL,  -- Option premium at entry
                entry_time TEXT NOT NULL,
                underlying_entry_price REAL NOT NULL,  -- Underlying price when entered
                target_price REAL NOT NULL,  -- 15% profit target
                stoploss_price REAL NOT NULL,  -- 5% stop loss
                current_price REAL,  -- Current option premium (updated by monitoring thread)
                exit_price REAL,  -- Option premium at exit
                exit_time TEXT,
                exit_reason TEXT,  -- 'TARGET', 'STOPLOSS', 'MANUAL'
                profit_loss REAL,  -- Profit/Loss amount
                profit_loss_percent REAL,  -- Profit/Loss percentage
                status TEXT NOT NULL DEFAULT 'OPEN',  -- 'OPEN', 'CLOSED'
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Migration: Handle schema changes for existing databases
        try:
            cursor.execute('PRAGMA table_info(level)')
            columns = [col[1] for col in cursor.fetchall()]
            
            # Check if level_number column exists (old schema)
            if 'level_number' in columns:
                print("Migrating level table: removing level_number column...")
                # Create new table without level_number
                cursor.execute('''
                    CREATE TABLE level_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        uuid TEXT UNIQUE NOT NULL,
                        user_id TEXT NOT NULL,
                        index_type TEXT NOT NULL,
                        level_value REAL NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        created_date TEXT NOT NULL
                    )
                ''')
                # Copy data (excluding level_number)
                cursor.execute('''
                    INSERT INTO level_new (id, uuid, user_id, index_type, level_value, created_at, updated_at, created_date)
                    SELECT id, uuid, user_id, index_type, level_value, created_at, updated_at, 
                           COALESCE(created_date, date('now'))
                    FROM level
                ''')
                cursor.execute('DROP TABLE level')
                cursor.execute('ALTER TABLE level_new RENAME TO level')
                conn.commit()
                print("Migration completed: removed level_number column")
            
            # Add created_date column if it doesn't exist
            if 'created_date' not in columns:
                cursor.execute('ALTER TABLE level ADD COLUMN created_date TEXT')
                # Set created_date for existing records
                cursor.execute('UPDATE level SET created_date = date(created_at) WHERE created_date IS NULL OR created_date = ""')
                conn.commit()
                print("Added created_date column to level table")
        except Exception as e:
            print(f"Migration check completed (or not needed): {e}")
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
        
        # Load entry prices from database into cache
        load_entry_prices_from_db()
        
    except Exception as e:
        print(f"Error initializing database: {e}")

def save_level(user_id, index_type, level_value, level_uuid=None):
    """Save a level to the database (allows dynamic levels, not just 1-3)"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        current_date = datetime.now().date().isoformat()  # Date for daily refresh
        
        # If UUID provided, update existing level; otherwise create new one
        if level_uuid:
            cursor.execute('''
                SELECT uuid FROM level 
                WHERE uuid = ? AND user_id = ?
            ''', (level_uuid, user_id))
            
            if cursor.fetchone():
                # Update existing level
                cursor.execute('''
                    UPDATE level 
                    SET level_value = ?, updated_at = ?
                    WHERE uuid = ? AND user_id = ?
                ''', (level_value, current_time, level_uuid, user_id))
            else:
                return False  # UUID not found
        else:
            # Create new level
            level_uuid = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO level 
                (uuid, user_id, index_type, level_value, created_at, updated_at, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (level_uuid, user_id, index_type, level_value, current_time, current_time, current_date))
        
        conn.commit()
        conn.close()
        print(f"Level saved with UUID: {level_uuid}")
        return level_uuid
    except Exception as e:
        print(f"Error saving level: {e}")
        return None

def get_levels(user_id, index_type=None, today_only=False):
    """Get all levels for a user (returns as list, not fixed 1-3 structure)
    
    Args:
        user_id: User ID
        index_type: Optional filter by index type ('BANK_NIFTY' or 'NIFTY_50')
        today_only: If True, only return levels created today
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        if index_type:
            if today_only:
                cursor.execute('''
                    SELECT uuid, index_type, level_value, updated_at, created_date
                    FROM level 
                    WHERE user_id = ? AND index_type = ? AND created_date = ?
                    ORDER BY level_value DESC
                ''', (user_id, index_type, today))
            else:
                cursor.execute('''
                    SELECT uuid, index_type, level_value, updated_at, created_date
                    FROM level 
                    WHERE user_id = ? AND index_type = ?
                    ORDER BY level_value DESC
                ''', (user_id, index_type))
        else:
            if today_only:
                cursor.execute('''
                    SELECT uuid, index_type, level_value, updated_at, created_date
                    FROM level 
                    WHERE user_id = ? AND created_date = ?
                    ORDER BY index_type, level_value DESC
                ''', (user_id, today))
            else:
                cursor.execute('''
                    SELECT uuid, index_type, level_value, updated_at, created_date
                    FROM level 
                    WHERE user_id = ?
                    ORDER BY index_type, level_value DESC
                ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert to dictionary format with lists instead of fixed 1-3 structure
        levels = {
            'BANK_NIFTY': [],
            'NIFTY_50': []
        }
        
        for row in results:
            level_uuid, idx_type, level_value, updated_at, created_date = row
            levels[idx_type].append({
                'uuid': level_uuid,
                'value': level_value,
                'updated_at': updated_at,
                'created_date': created_date
            })
        
        return levels
    except Exception as e:
        print(f"Error getting levels: {e}")
        return {
            'BANK_NIFTY': [],
            'NIFTY_50': []
        }

def clear_levels_for_today(user_id):
    """Clear all levels created today (for daily refresh)"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        cursor.execute('''
            DELETE FROM level 
            WHERE user_id = ? AND created_date = ?
        ''', (user_id, today))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"Cleared {deleted_count} levels for today")
        return deleted_count
    except Exception as e:
        print(f"Error clearing levels for today: {e}")
        return 0

def clear_all_levels(user_id, index_type=None):
    """Clear all levels for a user (or specific index type)"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        if index_type:
            cursor.execute('''
                DELETE FROM level 
                WHERE user_id = ? AND index_type = ?
            ''', (user_id, index_type))
        else:
            cursor.execute('''
                DELETE FROM level 
                WHERE user_id = ?
            ''', (user_id,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"Cleared {deleted_count} levels")
        return deleted_count
    except Exception as e:
        print(f"Error clearing levels: {e}")
        return 0

def load_entry_prices_from_db(user_id='default_user'):
    """
    Load entry prices from database into cache (optimized - reads once).
    This function should be called on startup and when entry prices are updated.
    
    Args:
        user_id: User ID to fetch entry prices for
    
    Returns:
        dict: Dictionary with entry prices {'NIFTY_50': price, 'NIFTY_BANK': price}
    """
    global entry_prices_cache
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Fetch all entry prices for the user
        cursor.execute('''
            SELECT instrument, entry_price
            FROM entry_prices
            WHERE user_id = ?
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Update cache
        entry_prices_cache = {
            'NIFTY_50': None,
            'NIFTY_BANK': None
        }
        
        for instrument, entry_price in results:
            if instrument in entry_prices_cache:
                entry_prices_cache[instrument] = float(entry_price)
        
        print(f"Loaded entry prices from DB: NIFTY_50={entry_prices_cache['NIFTY_50']}, NIFTY_BANK={entry_prices_cache['NIFTY_BANK']}")
        return entry_prices_cache
        
    except Exception as e:
        print(f"Error loading entry prices from database: {e}")
        return entry_prices_cache

def save_entry_price_to_db(user_id, instrument, entry_price):
    """
    Save entry price to database and update cache.
    
    Args:
        user_id: User ID
        instrument: 'NIFTY_50' or 'NIFTY_BANK'
        entry_price: Entry price value
    
    Returns:
        bool: True if successful, False otherwise
    """
    global entry_prices_cache
    
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        # Insert or update entry price
        cursor.execute('''
            INSERT OR REPLACE INTO entry_prices 
            (user_id, instrument, entry_price, created_at, updated_at)
            VALUES (?, ?, ?, 
                COALESCE((SELECT created_at FROM entry_prices WHERE user_id = ? AND instrument = ?), ?),
                ?)
        ''', (user_id, instrument, entry_price, user_id, instrument, current_time, current_time))
        
        conn.commit()
        conn.close()
        
        # Update cache immediately
        if instrument in entry_prices_cache:
            entry_prices_cache[instrument] = float(entry_price)
        
        print(f"Saved entry price to DB: {instrument} = {entry_price}")
        return True
        
    except Exception as e:
        print(f"Error saving entry price to database: {e}")
        return False


def check_levels_for_today(user_id):
    """Check if any levels have been touched today"""


def store_alert_response(alert_data, kite_response):
    """Store alert response in database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Extract data from KITE response - handle different response structures
        response_data = {}
        if 'response' in kite_response and 'data' in kite_response['response']:
            # Structure: {"response": {"data": {...}}}
            response_data = kite_response['response']['data']
        elif 'data' in kite_response:
            # Structure: {"data": {...}}
            response_data = kite_response['data']
        else:
            # Fallback: use the entire response
            response_data = kite_response
        
        print(f"Debug - KITE response structure: {kite_response}")
        print(f"Debug - Extracted response_data: {response_data}")
        
        # Validate that we have required data
        if not response_data or not response_data.get('uuid'):
            print("Error: No valid response data or UUID found")
            return False
        
        cursor.execute('''
            INSERT OR REPLACE INTO alerts (
                uuid, name, user_id, lhs_exchange, lhs_tradingsymbol, lhs_attribute,
                operator, rhs_type, rhs_constant, rhs_exchange, rhs_tradingsymbol,
                rhs_attribute, type, status, alert_count, disabled_reason,
                created_at, updated_at, stored_at, kite_response
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            response_data.get('uuid'),
            response_data.get('name'),
            response_data.get('user_id'),
            response_data.get('lhs_exchange'),
            response_data.get('lhs_tradingsymbol'),
            response_data.get('lhs_attribute'),
            response_data.get('operator'),
            response_data.get('rhs_type'),
            response_data.get('rhs_constant'),
            response_data.get('rhs_exchange'),
            response_data.get('rhs_tradingsymbol'),
            response_data.get('rhs_attribute'),
            response_data.get('type'),
            response_data.get('status'),
            response_data.get('alert_count'),
            response_data.get('disabled_reason'),
            response_data.get('created_at'),
            response_data.get('updated_at'),
            datetime.now().isoformat(),
            json.dumps(kite_response)
        ))
        
        conn.commit()
        conn.close()
        print(f"Alert stored in database: {response_data.get('uuid')}")
        return True
        
    except Exception as e:
        print(f"Error storing alert in database: {e}")
        return False

def get_stored_alerts():
    """Retrieve all stored alerts from database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uuid, name, user_id, lhs_exchange, lhs_tradingsymbol, lhs_attribute,
                   operator, rhs_type, rhs_constant, rhs_exchange, rhs_tradingsymbol,
                   rhs_attribute, type, status, alert_count, disabled_reason,
                   created_at, updated_at, stored_at, last_triggered_at, last_triggered_price
            FROM alerts
            ORDER BY stored_at DESC
        ''')
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'uuid': row[0],
                'name': row[1],
                'user_id': row[2],
                'lhs_exchange': row[3],
                'lhs_tradingsymbol': row[4],
                'lhs_attribute': row[5],
                'operator': row[6],
                'rhs_type': row[7],
                'rhs_constant': row[8],
                'rhs_exchange': row[9],
                'rhs_tradingsymbol': row[10],
                'rhs_attribute': row[11],
                'type': row[12],
                'status': row[13],
                'alert_count': row[14],
                'disabled_reason': row[15],
                'created_at': row[16],
                'updated_at': row[17],
                'stored_at': row[18],
                'last_triggered_at': row[19],
                'last_triggered_price': row[20]
            })
        
        conn.close()
        return alerts
        
    except Exception as e:
        print(f"Error retrieving alerts from database: {e}")
        return []

def delete_alert_from_database(uuid):
    """Delete alert from local database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM alerts WHERE uuid = ?', (uuid,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"Alert deleted from database: {uuid}")
        else:
            print(f"Alert not found in database: {uuid}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error deleting alert from database: {e}")
        return False


# ============================================================================
# Session Management Functions
# ============================================================================

def load_session_data():
    """Load session data from file"""
    global user_api_key, user_api_secret, kite
    
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                data = json.load(f)
                user_api_key = data.get('api_key')
                user_api_secret = data.get('api_secret')
                access_token = data.get('access_token')
                
                if user_api_key and access_token:
                    kite = KiteConnect(api_key=user_api_key)
                    kite.set_access_token(access_token)
                    print("Loaded existing session from file")
                    return True
        except Exception as e:
            print(f"Error loading session: {e}")
    return False

def sync_session_from_file():
    """Sync Flask session with file-based session data"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                data = json.load(f)
                session['api_key'] = data.get('api_key')
                session['api_secret'] = data.get('api_secret')
                session['access_token'] = data.get('access_token')
                print("Synced session from file")
                return True
        except Exception as e:
            print(f"Error syncing session: {e}")
    return False

def save_session_data():
    """Save session data to file"""
    global user_api_key, user_api_secret
    try:
        data = {
            'api_key': user_api_key,
            'api_secret': user_api_secret,
            'access_token': session.get('access_token')
        }
        with open(SESSION_FILE, 'w') as f:
            json.dump(data, f)
        print("Session data saved to file")
    except Exception as e:
        print(f"Error saving session: {e}")


# ============================================================================
# Alert Processing Functions
# ============================================================================

def send_alert_to_kite(alert_data):
    """Send alert to KITE API"""
    try:
        # Get API credentials from session
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        if not api_key or not access_token:
            return {'error': 'Authentication required', 'success': False}
        
        # Prepare headers
        headers = {
            'X-Kite-Version': '3',
            'Authorization': f'token {api_key}:{access_token}'
        }
        
        # Send POST request to KITE alerts API
        response = requests.post(
            'https://api.kite.trade/alerts',
            headers=headers,
            data=alert_data
        )
        
        if response.status_code == 200:
            kite_response = response.json()
            # Store the alert response in database
            store_alert_response(alert_data, kite_response)
            return {'message': 'Alert created successfully', 'success': True, 'response': kite_response}
        else:
            return {'error': f'Failed to create alert: {response.text}', 'success': False}
            
    except Exception as e:
        return {'error': f'Error sending alert to KITE: {str(e)}', 'success': False}

def sync_alerts_with_zerodha():
    """Sync local database alerts with Zerodha - remove alerts that no longer exist in Zerodha"""
    global kite
    
    if not session.get('access_token') or not kite:
        print("Cannot sync alerts: Not authenticated")
        return False
    
    try:
        # Get API credentials from session
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        # Prepare headers
        headers = {
            'X-Kite-Version': '3',
            'Authorization': f'token {api_key}:{access_token}'
        }
        
        # Get alerts from Zerodha
        response = requests.get(
            'https://api.kite.trade/alerts',
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"Failed to fetch alerts from Zerodha: {response.text}")
            return False
        
        zerodha_data = response.json()
        zerodha_alerts = zerodha_data.get('data', [])
        zerodha_uuids = {alert['uuid'] for alert in zerodha_alerts}
        
        # Get alerts from local database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT uuid, name FROM alerts')
        db_alerts = cursor.fetchall()
        
        # Find alerts in database that are not in Zerodha
        alerts_to_delete = []
        for db_uuid, db_name in db_alerts:
            if db_uuid not in zerodha_uuids:
                alerts_to_delete.append((db_uuid, db_name))
        
        # Delete orphaned alerts from database
        deleted_count = 0
        for uuid, name in alerts_to_delete:
            cursor.execute('DELETE FROM alerts WHERE uuid = ?', (uuid,))
            if cursor.rowcount > 0:
                deleted_count += 1
                print(f"Deleted orphaned alert from database: {name} ({uuid})")
        
        if deleted_count > 0:
            conn.commit()
            print(f"Sync completed: {deleted_count} orphaned alerts removed from database")
        else:
            print("Sync completed: No orphaned alerts found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error syncing alerts with Zerodha: {e}")
        return False

def get_current_price_for_symbol(symbol):
    """Get current price for a given symbol"""
    global kite
    
    if not kite:
        return 0
    
    try:
        # Map symbol to KITE format
        kite_symbol = f"NSE:{symbol}"
        
        # Fetch current price
        quote_data = kite.quote(kite_symbol).get(kite_symbol, {})
        current_price = quote_data.get('last_price', 0)
        
        return current_price
        
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return 0

def get_instrument_type(symbol):
    """Get instrument type (NIFTY or BANK NIFTY) for display"""
    if symbol == 'NIFTY 50':
        return 'NIFTY'
    elif symbol == 'NIFTY BANK':
        return 'BANK NIFTY'
    else:
        return symbol

def check_price_touch_level(current_price, target_price, operator, previous_price=None):
    """Check if current price has crossed the alert level today and determine crossing direction"""
    if current_price == 0 or target_price == 0:
        return {'crossed': False, 'direction': None, 'status': 'no_data', 'crossed_today': False}
    
    # Check if price has crossed the level based on operator
    crossed = False
    direction = None
    crossed_today = False
    
    # Determine if we have a crossing (price moved from one side to the other)
    if previous_price and previous_price != current_price:
        if operator == '>=':
            # Crossed from below to above/at target
            if previous_price < target_price and current_price >= target_price:
                crossed = True
                crossed_today = True
                direction = 'up'  # Price crossed up from below
            # Crossed from above to below target
            elif previous_price >= target_price and current_price < target_price:
                crossed = True
                crossed_today = True
                direction = 'down'  # Price crossed down from above
        elif operator == '<=':
            # Crossed from above to below/at target
            if previous_price > target_price and current_price <= target_price:
                crossed = True
                crossed_today = True
                direction = 'down'  # Price crossed down from above
            # Crossed from below to above target
            elif previous_price <= target_price and current_price > target_price:
                crossed = True
                crossed_today = True
                direction = 'up'  # Price crossed up from below
        elif operator == '>':
            # Crossed from below/at to above target
            if previous_price <= target_price and current_price > target_price:
                crossed = True
                crossed_today = True
                direction = 'up'  # Price crossed up
            # Crossed from above to below/at target
            elif previous_price > target_price and current_price <= target_price:
                crossed = True
                crossed_today = True
                direction = 'down'  # Price crossed down
        elif operator == '<':
            # Crossed from above/at to below target
            if previous_price >= target_price and current_price < target_price:
                crossed = True
                crossed_today = True
                direction = 'down'  # Price crossed down
            # Crossed from below to above/at target
            elif previous_price < target_price and current_price >= target_price:
                crossed = True
                crossed_today = True
                direction = 'up'  # Price crossed up
        elif operator == '==':
            # For exact match, check if price crossed the exact level
            tolerance = 0.01
            if (abs(previous_price - target_price) > tolerance and 
                abs(current_price - target_price) <= tolerance):
                crossed = True
                crossed_today = True
                direction = 'up' if previous_price < target_price else 'down'
    
    # If no previous price, we can't determine crossing, but we can show current position
    if not previous_price:
        if operator == '>=' and current_price >= target_price:
            direction = 'above_or_at'
        elif operator == '<=' and current_price <= target_price:
            direction = 'below_or_at'
        elif operator == '>' and current_price > target_price:
            direction = 'above'
        elif operator == '<' and current_price < target_price:
            direction = 'below'
        elif operator == '==' and abs(current_price - target_price) <= 0.01:
            direction = 'at_level'
        else:
            if current_price > target_price:
                direction = 'above'
            else:
                direction = 'below'
    
    # Determine status
    if crossed:
        status = 'crossed'
    else:
        # Check how close we are to the target
        distance = abs(current_price - target_price)
        if distance <= target_price * 0.01:  # Within 1%
            status = 'close'
        else:
            status = 'far'
    
    return {
        'crossed': crossed,
        'crossed_today': crossed_today,
        'direction': direction,
        'status': status,
        'distance': abs(current_price - target_price),
        'distance_percent': abs(current_price - target_price) / target_price * 100 if target_price > 0 else 0,
        'current_price': current_price,
        'target_price': target_price,
        'operator': operator
    }

def check_alert_triggers():
    """Check if any stored alerts should be triggered based on current prices"""
    global kite
    try:
        # Get current prices
        if not kite:
            return []
        
        # Fetch current prices for NIFTY 50 and NIFTY BANK
        nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
        bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
        
        current_prices = {
            'NIFTY 50': nifty_data.get('last_price', 0),
            'NIFTY BANK': bank_nifty_data.get('last_price', 0)
        }
        
        # Get all active alerts from database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uuid, name, lhs_tradingsymbol, operator, rhs_constant, status, alert_count
            FROM alerts
            WHERE status = 'enabled' AND alert_count = 0
        ''')
        
        alerts = cursor.fetchall()
        triggered_alerts = []
        
        for alert in alerts:
            uuid, name, symbol, operator, target_value, status, alert_count = alert
            
            current_price = current_prices.get(symbol, 0)
            if current_price == 0:
                continue
            
            # Check if alert condition is met
            is_triggered = False
            if operator == '>=' and current_price >= target_value:
                is_triggered = True
            elif operator == '<=' and current_price <= target_value:
                is_triggered = True
            elif operator == '>' and current_price > target_value:
                is_triggered = True
            elif operator == '<' and current_price < target_value:
                is_triggered = True
            elif operator == '==' and abs(current_price - target_value) < 0.01:
                is_triggered = True
            
            if is_triggered:
                # Update alert status to triggered
                update_alert_trigger_status(uuid, current_price, alert_count + 1)
                triggered_alerts.append({
                    'uuid': uuid,
                    'name': name,
                    'symbol': symbol,
                    'current_price': current_price,
                    'target_price': target_value,
                    'operator': operator,
                    'triggered_at': datetime.now().isoformat()
                })
        
        conn.close()
        return triggered_alerts
        
    except Exception as e:
        print(f"Error checking alert triggers: {e}")
        return []

def update_alert_trigger_status(uuid, current_price, new_alert_count):
    """Update alert status when triggered - mark as triggered (one-time only)"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Update alert count to 1 (triggered once) and mark as triggered
        cursor.execute('''
            UPDATE alerts 
            SET alert_count = 1, 
                last_triggered_at = ?,
                last_triggered_price = ?,
                status = 'triggered'
            WHERE uuid = ?
        ''', (datetime.now().isoformat(), current_price, uuid))
        
        conn.commit()
        conn.close()
        
        print(f"Alert triggered once: {uuid} at price {current_price} - now marked as triggered")
        return True
        
    except Exception as e:
        print(f"Error updating alert trigger status: {e}")
        return False


# ============================================================================
# Trend Monitoring Background Thread
# ============================================================================

def trend_monitoring_worker():
    """
    Background thread worker that continuously monitors prices and checks for trend reversals.
    Runs in a loop, checking every second for trend reversals.
    """
    global trend_monitoring_running, nifty_prices, bank_nifty_prices
    
    print("📊 Trend monitoring background thread started")
    
    while trend_monitoring_running:
        try:
            # Check NIFTY 50 for trend reversals
            if len(nifty_prices) > 0:
                check_trend_reversal("NIFTY 50", "NIFTY_50", nifty_prices)
            
            # Check NIFTY BANK for trend reversals
            if len(bank_nifty_prices) > 0:
                check_trend_reversal("NIFTY BANK", "NIFTY_BANK", bank_nifty_prices)
            
            # Sleep for 1 second before next check
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in trend monitoring thread: {e}")
            time.sleep(1)  # Continue even if there's an error
    
    print("📊 Trend monitoring background thread stopped")


def start_trend_monitoring():
    """
    Start the background thread for trend reversal monitoring.
    This thread continuously monitors price deques and checks for trend reversals.
    """
    global trend_monitoring_running, trend_monitoring_thread
    
    if trend_monitoring_running:
        print("Trend monitoring thread already running")
        return
    
    trend_monitoring_running = True
    trend_monitoring_thread = threading.Thread(target=trend_monitoring_worker, daemon=True)
    trend_monitoring_thread.start()
    print("✅ Started trend monitoring background thread")


def stop_trend_monitoring():
    """
    Stop the background thread for trend reversal monitoring.
    """
    global trend_monitoring_running
    
    if not trend_monitoring_running:
        return
    
    trend_monitoring_running = False
    print("🛑 Stopping trend monitoring background thread")
    
    # Wait for thread to finish (with timeout)
    if trend_monitoring_thread and trend_monitoring_thread.is_alive():
        trend_monitoring_thread.join(timeout=2)


# ============================================================================
# Paper Trade Monitoring Background Thread
# ============================================================================

def paper_trade_monitoring_worker():
    """
    Background thread worker that continuously monitors paper trades and checks for target/stop loss.
    Uses WebSocket prices for real-time updates (as good as live trading).
    Runs in a loop, checking every second for paper trade exits.
    """
    global paper_trade_monitoring_running, kite, option_websocket_prices
    
    print("📝 Paper trade monitoring background thread started (using WebSocket prices)")
    
    while paper_trade_monitoring_running:
        try:
            # Get all open paper trades
            open_trades = get_paper_trades(status='OPEN')
            
            if not open_trades:
                time.sleep(2)  # Sleep shorter if no open trades
                continue
            
            # Check each open paper trade
            for trade in open_trades:
                try:
                    tradingsymbol = trade['tradingsymbol']
                    exchange = trade['exchange']
                    entry_price = trade['entry_price']
                    target_price = trade['target_price']
                    stoploss_price = trade['stoploss_price']
                    trade_uuid = trade['trade_uuid']
                    
                    # First, try to get price from WebSocket (real-time)
                    current_price = None
                    option_key = f"{exchange}:{tradingsymbol}"
                    
                    if option_key in option_websocket_prices:
                        ws_data = option_websocket_prices[option_key]
                        current_price = ws_data.get('last_price', 0)
                        # Use WebSocket price if available and recent (within last 10 seconds)
                        timestamp = ws_data.get('timestamp')
                        if timestamp:
                            try:
                                price_time = datetime.fromisoformat(timestamp)
                                time_diff = (datetime.now() - price_time).total_seconds()
                                if time_diff > 10:  # Price is stale, fallback to REST
                                    current_price = None
                            except:
                                pass
                    
                    # Fallback to REST API if WebSocket price not available
                    if current_price is None or current_price == 0:
                        if kite:
                            try:
                                option_quote = kite.quote(option_key)
                                option_data = option_quote.get(option_key, {})
                                current_price = option_data.get("last_price", 0)
                                
                                if current_price == 0:
                                    # Try to get from depth
                                    current_price = option_data.get("depth", [{}])[0].get("price", 0) if option_data.get("depth") else 0
                            except Exception as e:
                                # Silently continue if REST API fails
                                continue
                        else:
                            continue
                    
                    if current_price > 0:
                        # Update current price in database
                        update_paper_trade_current_price(trade_uuid, current_price)
                        
                        # Check if target is hit (15% profit)
                        if current_price >= target_price:
                            update_paper_trade_exit(trade_uuid, current_price, 'TARGET')
                            print(f"📝 Paper trade {trade_uuid} hit TARGET at {current_price:.2f} (WebSocket: {option_key in option_websocket_prices})")
                        
                        # Check if stop loss is hit (5% loss)
                        elif current_price <= stoploss_price:
                            update_paper_trade_exit(trade_uuid, current_price, 'STOPLOSS')
                            print(f"📝 Paper trade {trade_uuid} hit STOPLOSS at {current_price:.2f} (WebSocket: {option_key in option_websocket_prices})")
                        
                except Exception as e:
                    print(f"Error processing paper trade: {e}")
            
            # Sleep for 1 second before next check (faster for real-time monitoring)
            time.sleep(1)
            
        except Exception as e:
            print(f"Error in paper trade monitoring thread: {e}")
            time.sleep(1)  # Continue even if there's an error
    
    print("📝 Paper trade monitoring background thread stopped")


def subscribe_existing_paper_trades_to_websocket():
    """
    Subscribe to all existing open paper trades in WebSocket for real-time price tracking.
    This should be called when WebSocket is ready.
    """
    try:
        open_trades = get_paper_trades(status='OPEN')
        if not open_trades:
            return
        
        subscribed_count = 0
        for trade in open_trades:
            tradingsymbol = trade['tradingsymbol']
            exchange = trade['exchange']
            if subscribe_option_to_websocket(tradingsymbol, exchange):
                subscribed_count += 1
        
        if subscribed_count > 0:
            print(f"✅ Subscribed {subscribed_count} existing paper trades to WebSocket")
    except Exception as e:
        print(f"Error subscribing existing paper trades to WebSocket: {e}")


def start_paper_trade_monitoring():
    """
    Start the background thread for paper trade monitoring.
    This thread continuously monitors paper trades and checks for target/stop loss.
    """
    global paper_trade_monitoring_running, paper_trade_monitoring_thread
    
    if paper_trade_monitoring_running:
        print("Paper trade monitoring thread already running")
        return
    
    # Subscribe to existing open paper trades
    subscribe_existing_paper_trades_to_websocket()
    
    paper_trade_monitoring_running = True
    paper_trade_monitoring_thread = threading.Thread(target=paper_trade_monitoring_worker, daemon=True)
    paper_trade_monitoring_thread.start()
    print("✅ Started paper trade monitoring background thread")


def stop_paper_trade_monitoring():
    """
    Stop the background thread for paper trade monitoring.
    """
    global paper_trade_monitoring_running
    
    if not paper_trade_monitoring_running:
        return
    
    paper_trade_monitoring_running = False
    print("🛑 Stopping paper trade monitoring background thread")
    
    # Wait for thread to finish (with timeout)
    if paper_trade_monitoring_thread and paper_trade_monitoring_thread.is_alive():
        paper_trade_monitoring_thread.join(timeout=2)


def get_paper_trades(user_id='default_user', status=None, instrument=None):
    """
    Get paper trades from database.
    
    Args:
        user_id: User ID
        status: Filter by status ('OPEN', 'CLOSED') or None for all
        instrument: Filter by instrument ('NIFTY_50', 'NIFTY_BANK') or None for all
    
    Returns:
        list: List of paper trade dictionaries
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM paper_trades WHERE user_id = ?'
        params = [user_id]
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        if instrument:
            query += ' AND instrument = ?'
            params.append(instrument)
        
        query += ' ORDER BY entry_time DESC'
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        trades = []
        
        for row in cursor.fetchall():
            trade_dict = dict(zip(columns, row))
            trades.append(trade_dict)
        
        conn.close()
        return trades
        
    except Exception as e:
        print(f"Error getting paper trades: {e}")
        return []


def update_paper_trade_current_price(trade_uuid, current_price, user_id='default_user'):
    """
    Update current price for a paper trade.
    
    Args:
        trade_uuid: Trade UUID
        current_price: Current option premium
        user_id: User ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE paper_trades 
            SET current_price = ?, updated_at = ?
            WHERE trade_uuid = ? AND user_id = ? AND status = 'OPEN'
        ''', (current_price, current_time, trade_uuid, user_id))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error updating paper trade current price: {e}")
        return False


def update_paper_trade_exit(trade_uuid, exit_price, exit_reason, user_id='default_user'):
    """
    Update paper trade exit information when target or stop loss is hit.
    
    Args:
        trade_uuid: Trade UUID
        exit_price: Option premium at exit
        exit_reason: 'TARGET', 'STOPLOSS', or 'MANUAL'
        user_id: User ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Get trade entry details
        cursor.execute('''
            SELECT entry_price, quantity FROM paper_trades 
            WHERE trade_uuid = ? AND user_id = ? AND status = 'OPEN'
        ''', (trade_uuid, user_id))
        
        trade = cursor.fetchone()
        if not trade:
            print(f"Paper trade {trade_uuid} not found or already closed")
            conn.close()
            return False
        
        entry_price, quantity = trade
        
        # Calculate profit/loss
        profit_loss = (exit_price - entry_price) * quantity
        profit_loss_percent = ((exit_price - entry_price) / entry_price) * 100
        
        current_time = datetime.now().isoformat()
        
        # Update trade
        cursor.execute('''
            UPDATE paper_trades 
            SET exit_price = ?, exit_time = ?, exit_reason = ?,
                profit_loss = ?, profit_loss_percent = ?, status = 'CLOSED', updated_at = ?
            WHERE trade_uuid = ? AND user_id = ?
        ''', (exit_price, current_time, exit_reason, profit_loss, profit_loss_percent, 
              current_time, trade_uuid, user_id))
        
        conn.commit()
        conn.close()
        
        result = "PROFIT" if profit_loss > 0 else "LOSS"
        print(f"✅ Paper trade exit updated: {trade_uuid} - {result} of {abs(profit_loss):.2f} ({profit_loss_percent:.2f}%)")
        return True
        
    except Exception as e:
        print(f"Error updating paper trade exit: {e}")
        return False


# ============================================================================
# WebSocket Functions
# ============================================================================

def get_credentials_from_session_or_file():
    """Get API credentials from session or file-based storage"""
    global user_api_key
    api_key = None
    access_token = None
    
    # Only try to access session if we're in a request context
    if has_request_context():
        try:
            api_key = session.get('api_key')
            access_token = session.get('access_token')
        except RuntimeError:
            # Not in request context, skip session
            pass
    
    # If not in session, try global variables (loaded from file)
    if not api_key:
        api_key = user_api_key
    
    # If access_token not in session, try to load from file
    if not access_token:
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    data = json.load(f)
                    access_token = data.get('access_token')
                    if not api_key:
                        api_key = data.get('api_key')
            except Exception as e:
                print(f"Error loading credentials from file: {e}")
    
    return api_key, access_token

def get_instrument_tokens():
    """Get instrument tokens for NIFTY 50 and NIFTY BANK"""
    global kite
    
    if not kite:
        return None, None
    
    try:
        # Get all NSE instruments
        instruments = kite.instruments("NSE")
        
        # Find tokens for NIFTY 50 and NIFTY BANK
        nifty_token = None
        bank_nifty_token = None
        
        for instrument in instruments:
            if instrument['tradingsymbol'] == 'NIFTY 50':
                nifty_token = instrument['instrument_token']
            elif instrument['tradingsymbol'] == 'NIFTY BANK':
                bank_nifty_token = instrument['instrument_token']
            
            if nifty_token and bank_nifty_token:
                break
        
        return nifty_token, bank_nifty_token
    except Exception as e:
        print(f"Error getting instrument tokens: {e}")
        # Fallback to known tokens if API call fails
        return 256265, 260105  # Standard tokens for NIFTY 50 and NIFTY BANK

def fetch_nifty_prices_websocket(timeout=10):
    """
    Fetch Nifty 50 and Bank Nifty last traded prices using WebSocket.
    
    If continuous WebSocket is running, returns cached prices from it.
    Otherwise, falls back to REST API.
    
    Args:
        timeout (int): Maximum time to wait for prices in seconds (default: 10)
    
    Returns:
        dict: Dictionary containing last traded prices for NIFTY 50 and NIFTY BANK
              Format: {
                  'NIFTY 50': {'last_price': float, 'timestamp': str},
                  'NIFTY BANK': {'last_price': float, 'timestamp': str}
              }
    """
    global kite, kws, websocket_prices, continuous_websocket_running
    
    # If continuous WebSocket is running, use its cached prices
    if continuous_websocket_running:
        # Return cached prices from continuous WebSocket
        result = websocket_prices.copy()
        # If we have valid prices, return them
        if result['NIFTY 50']['last_price'] > 0 or result['NIFTY BANK']['last_price'] > 0:
            return result
        # Otherwise, wait a bit for prices to arrive
        time.sleep(1)
        result = websocket_prices.copy()
        if result['NIFTY 50']['last_price'] > 0 or result['NIFTY BANK']['last_price'] > 0:
            return result
    
    # If continuous WebSocket is not running, we can't create a temporary one
    # because it would conflict with Twisted reactor if continuous WebSocket starts later
    # Instead, fall back to REST API
    print("Continuous WebSocket not running, using REST API fallback")
    
    # Get credentials from session or file
    api_key, access_token = get_credentials_from_session_or_file()
    
    # Check if we have valid credentials
    if not api_key or not access_token:
        return {
            'NIFTY 50': {'last_price': 0, 'timestamp': None, 'error': 'Not authenticated. Please login first.'},
            'NIFTY BANK': {'last_price': 0, 'timestamp': None, 'error': 'Not authenticated. Please login first.'}
        }
    
    # Check if kite object is initialized, if not, initialize it
    global kite
    if not kite:
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
        except Exception as e:
            return {
                'NIFTY 50': {'last_price': 0, 'timestamp': None, 'error': f'Error initializing KiteConnect: {str(e)}'},
                'NIFTY BANK': {'last_price': 0, 'timestamp': None, 'error': f'Error initializing KiteConnect: {str(e)}'}
            }
    
    # Use REST API as fallback instead of creating temporary WebSocket
    try:
        nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
        bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
        
        return {
            'NIFTY 50': {
                'last_price': nifty_data.get('last_price', 0),
                'timestamp': nifty_data.get('timestamp', datetime.now().isoformat())
            },
            'NIFTY BANK': {
                'last_price': bank_nifty_data.get('last_price', 0),
                'timestamp': bank_nifty_data.get('timestamp', datetime.now().isoformat())
            }
        }
    except Exception as e:
        print(f"Error fetching prices via REST API: {e}")
        return {
            'NIFTY 50': {'last_price': 0, 'timestamp': None, 'error': str(e)},
            'NIFTY BANK': {'last_price': 0, 'timestamp': None, 'error': str(e)}
        }

def start_continuous_websocket():
    """Start a continuous WebSocket connection that broadcasts prices to all connected clients"""
    global continuous_kws, continuous_websocket_running, kite, socketio
    
    if continuous_websocket_running:
        print("Continuous WebSocket already running")
        return
    
    # Get credentials
    api_key, access_token = get_credentials_from_session_or_file()
    
    if not api_key or not access_token:
        print("Cannot start continuous WebSocket: No credentials")
        return
    
    # Ensure kite is initialized
    if not kite:
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
        except Exception as e:
            print(f"Error initializing KiteConnect for continuous WebSocket: {e}")
            return
    
    # Get instrument tokens
    nifty_token, bank_nifty_token = get_instrument_tokens()
    
    if not nifty_token or not bank_nifty_token:
        print("Cannot start continuous WebSocket: Could not get instrument tokens")
        return
    
    continuous_websocket_running = True
    
    def on_ticks(ws, ticks):
        """Callback to receive ticks and broadcast to all connected clients"""
        try:
            price_updates = {}
            global price_history, option_websocket_prices, option_token_to_symbol  # Access global variables
            
            for tick in ticks:
                instrument_token = tick['instrument_token']
                last_price = tick.get('last_price', 0)
                timestamp = datetime.now().isoformat()
                
                # Check if this is an option instrument (for paper trading)
                if instrument_token in option_token_to_symbol:
                    # This is an option instrument - update option_websocket_prices
                    option_info = option_token_to_symbol[instrument_token]
                    tradingsymbol = option_info['tradingsymbol']
                    exchange = option_info.get('exchange', 'NFO')
                    option_key = f"{exchange}:{tradingsymbol}"
                    option_websocket_prices[option_key] = {
                        'last_price': last_price,
                        'timestamp': timestamp
                    }
                    # Continue to next tick (don't process as underlying)
                    continue
                
                if instrument_token == nifty_token:
                    price_updates['nifty'] = {
                        'name': 'NIFTY 50',
                        'current_price': last_price,
                        'previous_close': websocket_prices['NIFTY 50'].get('previous_close', 0),
                        'last_updated': timestamp
                    }
                    websocket_prices['NIFTY 50'] = {
                        'last_price': last_price,
                        'timestamp': timestamp,
                        'previous_close': websocket_prices['NIFTY 50'].get('previous_close', 0)
                    }
                    # Append Nifty price to deque (for general history)
                    price_history.append({
                        'instrument': 'NIFTY 50',
                        'price': last_price,
                        'timestamp': timestamp
                    })
                    # Process tick for trend detection and entry logic
                    # Entry price will be fetched from cache (loaded from DB on startup)
                    on_tick(last_price, instrument="NIFTY 50")
                elif instrument_token == bank_nifty_token:
                    price_updates['bank_nifty'] = {
                        'name': 'NIFTY BANK',
                        'current_price': last_price,
                        'previous_close': websocket_prices['NIFTY BANK'].get('previous_close', 0),
                        'last_updated': timestamp
                    }
                    websocket_prices['NIFTY BANK'] = {
                        'last_price': last_price,
                        'timestamp': timestamp,
                        'previous_close': websocket_prices['NIFTY BANK'].get('previous_close', 0)
                    }
                    # Append Bank Nifty price to deque (for general history)
                    price_history.append({
                        'instrument': 'NIFTY BANK',
                        'price': last_price,
                        'timestamp': timestamp
                    })
                    # Process tick for trend detection and entry logic
                    # Entry price will be fetched from cache (loaded from DB on startup)
                    on_tick(last_price, instrument="NIFTY BANK")
            
            # Broadcast price updates to all connected clients
            if price_updates:
                # Calculate change/change_percent from WebSocket data (no REST API call needed)
                if 'nifty' in price_updates:
                    previous_close = websocket_prices['NIFTY 50'].get('previous_close', 0)
                    current_price = price_updates['nifty']['current_price']
                    if previous_close > 0:
                        change = current_price - previous_close
                        change_percent = (change / previous_close) * 100
                        price_updates['nifty']['change'] = change
                        price_updates['nifty']['change_percent'] = change_percent
                    else:
                        price_updates['nifty']['change'] = 0
                        price_updates['nifty']['change_percent'] = 0
                
                if 'bank_nifty' in price_updates:
                    previous_close = websocket_prices['NIFTY BANK'].get('previous_close', 0)
                    current_price = price_updates['bank_nifty']['current_price']
                    if previous_close > 0:
                        change = current_price - previous_close
                        change_percent = (change / previous_close) * 100
                        price_updates['bank_nifty']['change'] = change
                        price_updates['bank_nifty']['change_percent'] = change_percent
                    else:
                        price_updates['bank_nifty']['change'] = 0
                        price_updates['bank_nifty']['change_percent'] = 0
                
                # Emit to all connected clients
                if socketio:
                    socketio.emit('price_update', price_updates)
                
        except Exception as e:
            print(f"Error processing ticks in continuous WebSocket: {e}")
    
    def on_connect(ws, response):
        """Callback on successful connect"""
        try:
            print("Continuous WebSocket connected, subscribing to instruments...")
            # Subscribe to NIFTY 50 and NIFTY BANK
            ws.subscribe([nifty_token, bank_nifty_token])
            # Set mode to LTP (Last Traded Price) for both
            ws.set_mode(ws.MODE_LTP, [nifty_token, bank_nifty_token])
            print("Subscribed to NIFTY 50 and NIFTY BANK")
            
            # Subscribe to existing open paper trades for real-time price tracking
            subscribe_existing_paper_trades_to_websocket()
            
            # Get previous day's close price once (for calculating change/change_percent)
            try:
                global kite
                if kite:
                    nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
                    bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
                    
                    previous_close_nifty = nifty_data.get('ohlc', {}).get('close', 0)
                    previous_close_bank = bank_nifty_data.get('ohlc', {}).get('close', 0)
                    
                    websocket_prices['NIFTY 50']['previous_close'] = previous_close_nifty
                    websocket_prices['NIFTY BANK']['previous_close'] = previous_close_bank
                    
                    print(f"Stored previous close prices - NIFTY 50: {previous_close_nifty}, NIFTY BANK: {previous_close_bank}")
            except Exception as e:
                print(f"Error fetching previous close prices: {e}")
        except Exception as e:
            print(f"Error in continuous WebSocket on_connect: {e}")
    
    def on_close(ws, code, reason):
        """Callback on connection close"""
        global continuous_websocket_running, continuous_kws
        print(f"Continuous WebSocket closed: {code} - {reason}")
        continuous_websocket_running = False
        continuous_kws = None
        # Note: Don't try to reconnect automatically as Twisted reactor can't be restarted
        # The WebSocket will need to be restarted manually or on next server restart
        print("WebSocket closed. Restart server to reconnect.")
    
    def on_error(ws, code, reason):
        """Callback on error"""
        print(f"Continuous WebSocket error: {code} - {reason}")
    
    def connect_websocket():
        """Connect WebSocket in a separate thread"""
        global continuous_kws, continuous_websocket_running
        try:
            # Check if already running to prevent multiple starts
            if continuous_kws is not None:
                print("WebSocket already initialized, skipping...")
                return
                
            continuous_kws = KiteTicker(api_key, access_token)
            continuous_kws.on_ticks = on_ticks
            continuous_kws.on_connect = on_connect
            continuous_kws.on_close = on_close
            continuous_kws.on_error = on_error
            
            print("Starting continuous WebSocket connection...")
            # Use threaded=True to run in separate thread (required for Twisted reactor)
            continuous_kws.connect(threaded=True)
        except Exception as e:
            print(f"Error connecting continuous WebSocket: {e}")
            continuous_websocket_running = False
            continuous_kws = None
    
    # Start WebSocket connection in a daemon thread
    global continuous_websocket_thread
    continuous_websocket_thread = threading.Thread(target=connect_websocket, daemon=True)
    continuous_websocket_thread.start()

