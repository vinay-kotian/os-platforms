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

# Global WebSocket ticker instance
kws = None
continuous_websocket_running = False
continuous_websocket_thread = None
continuous_kws = None

# Dictionary to store previous prices for alert crossing detection
alert_previous_prices = {}


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
            global price_history  # Access the global price_history deque
            
            for tick in ticks:
                instrument_token = tick['instrument_token']
                last_price = tick.get('last_price', 0)
                timestamp = datetime.now().isoformat()
                
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
                    # Append Nifty price to deque
                    price_history.append({
                        'instrument': 'NIFTY 50',
                        'price': last_price,
                        'timestamp': timestamp
                    })
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
                    # Append Bank Nifty price to deque
                    price_history.append({
                        'instrument': 'NIFTY BANK',
                        'price': last_price,
                        'timestamp': timestamp
                    })
            
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

