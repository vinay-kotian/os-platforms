import os
import sys
import logging
import threading
import time
import requests
import sqlite3
import json
from datetime import datetime
from flask import Flask, redirect, request, session, url_for, render_template, flash
from flask.json import jsonify
from flask_socketio import SocketIO, emit
from kiteconnect import KiteConnect

# Import all supporting functions from services module
from services import (
    # Database functions
    init_database, save_level, get_levels, clear_levels_for_today, clear_all_levels,
    store_alert_response, get_stored_alerts, delete_alert_from_database,
    # Session management
    load_session_data, sync_session_from_file, save_session_data,
    # Alert functions
    send_alert_to_kite, sync_alerts_with_zerodha, get_current_price_for_symbol,
    get_instrument_type, check_price_touch_level, check_alert_triggers,
    update_alert_trigger_status,
    # WebSocket functions
    fetch_nifty_prices_websocket, start_continuous_websocket,
    get_credentials_from_session_or_file,
    # Global variables (imported for access)
    user_api_key, user_api_secret, kite, price_history, websocket_prices,
    alert_previous_prices, continuous_websocket_running, continuous_kws
)

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = "thisisasecretkey"   # needed for session handling
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Set socketio in services module so WebSocket functions can use it
import services
services.socketio = socketio

# Initialize database and load existing session on startup
init_database()
load_session_data()

@app.before_request
def before_request():
    """Sync session from file before each request"""
    if not session.get('access_token') and os.path.exists(services.SESSION_FILE):
        sync_session_from_file()

# Register authentication blueprint
login_required = None
get_current_user_id = None

try:
    from app.auth.routes import auth_bp
    from app.auth.middleware import login_required, get_current_user_id
    app.register_blueprint(auth_bp)
    print("✓ Auth blueprint registered successfully")
except ImportError as e:
    # Fallback if auth module not available
    print(f"Warning: Auth module not found, using default user. Error: {e}")
    import traceback
    traceback.print_exc()
    
    def login_required(f):
        return f
    
    def get_current_user_id():
        return 'default_user'
except Exception as e:
    print(f"Error registering auth blueprint: {e}")
    import traceback
    traceback.print_exc()
    # Still provide fallback functions
    def login_required(f):
        return f
    def get_current_user_id():
        return 'default_user'

# Ensure functions are defined even if import failed
if login_required is None:
    def login_required(f):
        return f

if get_current_user_id is None:
    def get_current_user_id():
        return 'default_user'

@app.route('/')
def index():
    """Home page - redirect based on login status"""
    # Check if user is logged in (has user session)
    if session.get('user_id'):
        # Check if Zerodha is connected
        if session.get('access_token') and kite:
            # User is logged in and Zerodha connected, redirect to prices page
            return redirect(url_for('prices'))
        else:
            # User logged in but Zerodha not connected, show Zerodha login
            return redirect(url_for('auth.zerodha_login'))
    else:
        # User not logged in, redirect to auth login
        return redirect(url_for('auth.login'))

# Zerodha routes moved to app/auth/routes.py

@app.route('/prices')
@login_required
def prices():
    """Nifty and Bank Nifty prices page"""
    global kite
    
    # Get current user ID
    user_id = get_current_user_id()
    
    # Get credentials from session or file
    api_key, access_token = get_credentials_from_session_or_file()
    
    # Check if user is logged in (either via session or file)
    if not api_key or not access_token:
        flash('Please connect your Zerodha account to view live stock prices', 'error')
        return redirect(url_for('auth.zerodha_login'))
    
    # Ensure kite is initialized
    if not kite:
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
        except Exception as e:
            flash(f'Error initializing KiteConnect: {str(e)}', 'error')
            return render_template('prices.html', prices=None)
    
    try:
        # Fetch live prices using WebSocket
        websocket_prices_data = fetch_nifty_prices_websocket(timeout=10)
        
        # Check if we got valid prices
        nifty_price = websocket_prices_data.get('NIFTY 50', {}).get('last_price', 0)
        bank_nifty_price = websocket_prices_data.get('NIFTY BANK', {}).get('last_price', 0)
        
        # If WebSocket failed, fallback to REST API
        if nifty_price == 0 or bank_nifty_price == 0:
            # Fallback to REST API
            nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
            bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
            
            prices_data = {
                'nifty': {
                    'name': nifty_data.get('tradingsymbol', 'NIFTY 50'),
                    'current_price': nifty_data.get('last_price', 0),
                    'change': nifty_data.get('net_change', 0),
                    'change_percent': nifty_data.get('net_change', 0) / nifty_data.get('ohlc', {}).get('close', 1) * 100 if nifty_data.get('ohlc', {}).get('close') else 0,
                    'last_updated': nifty_data.get('timestamp', 'N/A')
                },
                'bank_nifty': {
                    'name': bank_nifty_data.get('tradingsymbol', 'NIFTY BANK'),
                    'current_price': bank_nifty_data.get('last_price', 0),
                    'change': bank_nifty_data.get('net_change', 0),
                    'change_percent': bank_nifty_data.get('net_change', 0) / bank_nifty_data.get('ohlc', {}).get('close', 1) * 100 if bank_nifty_data.get('ohlc', {}).get('close') else 0,
                    'last_updated': bank_nifty_data.get('timestamp', 'N/A')
                }
            }
        else:
            # Use WebSocket data - need to get additional info from REST API for change/change_percent
            try:
                nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
                bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
                
                prices_data = {
                    'nifty': {
                        'name': 'NIFTY 50',
                        'current_price': nifty_price,
                        'change': nifty_data.get('net_change', 0),
                        'change_percent': nifty_data.get('net_change', 0) / nifty_data.get('ohlc', {}).get('close', 1) * 100 if nifty_data.get('ohlc', {}).get('close') else 0,
                        'last_updated': websocket_prices_data.get('NIFTY 50', {}).get('timestamp', 'N/A')
                    },
                    'bank_nifty': {
                        'name': 'NIFTY BANK',
                        'current_price': bank_nifty_price,
                        'change': bank_nifty_data.get('net_change', 0),
                        'change_percent': bank_nifty_data.get('net_change', 0) / bank_nifty_data.get('ohlc', {}).get('close', 1) * 100 if bank_nifty_data.get('ohlc', {}).get('close') else 0,
                        'last_updated': websocket_prices_data.get('NIFTY BANK', {}).get('timestamp', 'N/A')
                    }
                }
            except:
                # If REST API fails, use WebSocket data only
                prices_data = {
                    'nifty': {
                        'name': 'NIFTY 50',
                        'current_price': nifty_price,
                        'change': 0,
                        'change_percent': 0,
                        'last_updated': websocket_prices_data.get('NIFTY 50', {}).get('timestamp', 'N/A')
                    },
                    'bank_nifty': {
                        'name': 'NIFTY BANK',
                        'current_price': bank_nifty_price,
                        'change': 0,
                        'change_percent': 0,
                        'last_updated': websocket_prices_data.get('NIFTY BANK', {}).get('timestamp', 'N/A')
                    }
                }
        
        # Get Zerodha tokens from session if available
        access_token_display = session.get('access_token') or access_token
        request_token = session.get('request_token')
        
        return render_template('prices.html', prices=prices_data, access_token=access_token_display, request_token=request_token)
        
    except Exception as e:
        flash(f'Error fetching stock prices: {str(e)}', 'error')
        return render_template('prices.html', prices=None)

@app.route('/stocks/fetch-price')
def fetch_prices():
    """API endpoint to fetch current stock prices (DEPRECATED - use /stocks/fetch-price-websocket or WebSocket)"""
    # For backward compatibility, call the WebSocket endpoint function
    return fetch_prices_websocket()

@app.route('/stocks/fetch-price-websocket', methods=['GET'])
def fetch_prices_websocket():
    """API endpoint to fetch current stock prices using WebSocket"""
    global kite
    
    # Get credentials from session or file
    api_key, access_token = get_credentials_from_session_or_file()
    
    # Check if user is logged in (either via session or file)
    if not api_key or not access_token:
        return jsonify({'error': 'Not authenticated. Please login first at /login'}), 401
    
    # Ensure kite is initialized
    global kite
    if not kite:
        try:
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
        except Exception as e:
            return jsonify({'error': f'Error initializing KiteConnect: {str(e)}'}), 500
    
    try:
        # Fetch prices using WebSocket
        websocket_prices_data = fetch_nifty_prices_websocket(timeout=10)
        
        # Get additional data (change, change_percent) from REST API
        nifty_price = websocket_prices_data.get('NIFTY 50', {}).get('last_price', 0)
        bank_nifty_price = websocket_prices_data.get('NIFTY BANK', {}).get('last_price', 0)
        
        # Get change data from REST API
        try:
            nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
            bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
            
            # Format the data to match the template structure
            formatted_data = {
                'nifty': {
                    'name': 'NIFTY 50',
                    'current_price': nifty_price if nifty_price > 0 else nifty_data.get('last_price', 0),
                    'change': nifty_data.get('net_change', 0),
                    'change_percent': nifty_data.get('net_change', 0) / nifty_data.get('ohlc', {}).get('close', 1) * 100 if nifty_data.get('ohlc', {}).get('close') else 0,
                    'last_updated': websocket_prices_data.get('NIFTY 50', {}).get('timestamp', nifty_data.get('timestamp', 'N/A')),
                    'error': websocket_prices_data.get('NIFTY 50', {}).get('error')
                },
                'bank_nifty': {
                    'name': 'NIFTY BANK',
                    'current_price': bank_nifty_price if bank_nifty_price > 0 else bank_nifty_data.get('last_price', 0),
                    'change': bank_nifty_data.get('net_change', 0),
                    'change_percent': bank_nifty_data.get('net_change', 0) / bank_nifty_data.get('ohlc', {}).get('close', 1) * 100 if bank_nifty_data.get('ohlc', {}).get('close') else 0,
                    'last_updated': websocket_prices_data.get('NIFTY BANK', {}).get('timestamp', bank_nifty_data.get('timestamp', 'N/A')),
                    'error': websocket_prices_data.get('NIFTY BANK', {}).get('error')
                }
            }
        except Exception as e:
            # If REST API fails, return WebSocket data only
            formatted_data = {
                'nifty': {
                    'name': 'NIFTY 50',
                    'current_price': nifty_price,
                    'change': 0,
                    'change_percent': 0,
                    'last_updated': websocket_prices_data.get('NIFTY 50', {}).get('timestamp', 'N/A'),
                    'error': websocket_prices_data.get('NIFTY 50', {}).get('error')
                },
                'bank_nifty': {
                    'name': 'NIFTY BANK',
                    'current_price': bank_nifty_price,
                    'change': 0,
                    'change_percent': 0,
                    'last_updated': websocket_prices_data.get('NIFTY BANK', {}).get('timestamp', 'N/A'),
                    'error': websocket_prices_data.get('NIFTY BANK', {}).get('error')
                }
            }
        
        return jsonify(formatted_data)
        
    except Exception as e:
        return jsonify({'error': f'Error fetching stock prices via WebSocket: {str(e)}'}), 500

@app.route('/alerts/create', methods=['POST'])
def create_alert():
    """API endpoint to create alerts and send to KITE API"""
    global kite
    
    # Debug session info
    print(f"Session data: api_key={session.get('api_key')}, access_token={'***' if session.get('access_token') else None}")
    print(f"Global kite object: {kite is not None}")
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({
            'error': 'Not authenticated', 
            'debug': {
                'has_access_token': bool(session.get('access_token')),
                'has_kite': kite is not None,
                'session_keys': list(session.keys())
            }
        }), 401
    
    try:
        # Get alert data from request
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'lhs_exchange', 'lhs_tradingsymbol', 'lhs_attribute', 'operator', 'rhs_type', 'type']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Validate operator
        valid_operators = ['>=', '<=', '>', '<', '==', '!=']
        if data.get('operator') not in valid_operators:
            return jsonify({'error': f'Invalid operator. Must be one of: {", ".join(valid_operators)}'}), 400
        
        # Validate rhs_type
        valid_rhs_types = ['constant', 'variable']
        if data.get('rhs_type') not in valid_rhs_types:
            return jsonify({'error': f'Invalid rhs_type. Must be one of: {", ".join(valid_rhs_types)}'}), 400
        
        # If rhs_type is constant, validate rhs_constant
        if data.get('rhs_type') == 'constant' and 'rhs_constant' not in data:
            return jsonify({'error': 'rhs_constant is required when rhs_type is constant'}), 400
        
        # If rhs_type is variable, validate rhs_variable fields
        if data.get('rhs_type') == 'variable':
            variable_fields = ['rhs_exchange', 'rhs_tradingsymbol', 'rhs_attribute']
            missing_variable_fields = [field for field in variable_fields if field not in data]
            if missing_variable_fields:
                return jsonify({'error': f'Missing required fields for variable rhs_type: {", ".join(missing_variable_fields)}'}), 400
        
        # Send alert to KITE API
        result = send_alert_to_kite(data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({'error': f'Error creating alert: {str(e)}'}), 500

@app.route('/alerts', methods=['GET'])
def get_alerts():
    """API endpoint to get all alerts from KITE API with automatic sync"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # First, sync alerts to remove any orphaned alerts from database
        sync_alerts_with_zerodha()
        
        # Get API credentials from session
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        # Prepare headers
        headers = {
            'X-Kite-Version': '3',
            'Authorization': f'token {api_key}:{access_token}'
        }
        
        # Send GET request to KITE alerts API
        response = requests.get(
            'https://api.kite.trade/alerts',
            headers=headers
        )
        
        if response.status_code == 200:
            return jsonify({'alerts': response.json(), 'success': True}), 200
        else:
            return jsonify({'error': f'Failed to fetch alerts: {response.text}', 'success': False}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error fetching alerts: {str(e)}'}), 500

@app.route('/alerts/stored', methods=['GET'])
def get_stored_alerts_endpoint():
    """API endpoint to get all stored alerts from database"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        alerts = get_stored_alerts()
        return jsonify({
            'alerts': alerts,
            'count': len(alerts),
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving stored alerts: {str(e)}'}), 500

@app.route('/alerts/stored/<uuid>', methods=['GET'])
def get_stored_alert_by_uuid(uuid):
    """API endpoint to get a specific stored alert by UUID"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        import sqlite3
        import json
        conn = sqlite3.connect(services.DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uuid, name, user_id, lhs_exchange, lhs_tradingsymbol, lhs_attribute,
                   operator, rhs_type, rhs_constant, rhs_exchange, rhs_tradingsymbol,
                   rhs_attribute, type, status, alert_count, disabled_reason,
                   created_at, updated_at, stored_at, kite_response
            FROM alerts
            WHERE uuid = ?
        ''', (uuid,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            alert = {
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
                'kite_response': json.loads(row[19])
            }
            return jsonify({'alert': alert, 'success': True}), 200
        else:
            return jsonify({'error': 'Alert not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error retrieving alert: {str(e)}'}), 500

@app.route('/alerts/check-triggers', methods=['GET'])
def check_alert_triggers_endpoint():
    """API endpoint to check for triggered alerts"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        triggered_alerts = check_alert_triggers()
        return jsonify({
            'triggered_alerts': triggered_alerts,
            'count': len(triggered_alerts),
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error checking alert triggers: {str(e)}'}), 500

@app.route('/alerts/delete/<uuid>', methods=['DELETE'])
def delete_alert(uuid):
    """API endpoint to delete an alert by UUID"""
    global kite
    
    print(f"Delete alert request for UUID: {uuid}")
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        print("Delete failed: Not authenticated")
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        import requests
        # Get API credentials from session
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        print(f"Using API key: {api_key[:10]}... and access token: {access_token[:10]}...")
        
        # Prepare headers
        headers = {
            'X-Kite-Version': '3',
            'Authorization': f'token {api_key}:{access_token}'
        }
        
        # Send DELETE request to KITE alerts API
        print(f"Sending DELETE request to: https://api.kite.trade/alerts/{uuid}")
        response = requests.delete(
            f'https://api.kite.trade/alerts/{uuid}',
            headers=headers
        )
        
        print(f"KITE API response status: {response.status_code}")
        print(f"KITE API response text: {response.text}")
        
        if response.status_code == 200:
            # Also delete from local database
            delete_alert_from_database(uuid)
            print(f"Alert {uuid} deleted successfully from both KITE and database")
            return jsonify({'message': 'Alert deleted successfully', 'success': True}), 200
        else:
            print(f"Failed to delete alert from KITE: {response.text}")
            return jsonify({'error': f'Failed to delete alert: {response.text}', 'success': False}), 500
            
    except Exception as e:
        print(f"Exception during alert deletion: {str(e)}")
        return jsonify({'error': f'Error deleting alert: {str(e)}'}), 500

@app.route('/alerts/sync', methods=['POST'])
def sync_alerts():
    """API endpoint to manually sync alerts with Zerodha"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        success = sync_alerts_with_zerodha()
        if success:
            return jsonify({'message': 'Alerts synced successfully', 'success': True}), 200
        else:
            return jsonify({'error': 'Failed to sync alerts', 'success': False}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error syncing alerts: {str(e)}'}), 500

@app.route('/alerts/prices', methods=['GET'])
def get_alert_prices():
    """API endpoint to get current prices for all alerts with crossing detection"""
    global kite, alert_previous_prices
    
    # Check if user is logged in and kite is initialized
    if not session.get('access_token'):
        return jsonify({'error': 'Not authenticated - no access token'}), 401
    
    if not kite:
        return jsonify({'error': 'KiteConnect not initialized'}), 401
    
    try:
        # Use the global kite object to fetch alerts
        alerts_data = kite.alerts
        alerts = alerts_data.get('data', [])
        
        # Fetch current prices for each alert
        alerts_with_prices = []
        for alert in alerts:
            symbol = alert.get('lhs_tradingsymbol', '')
            current_price = get_current_price_for_symbol(symbol)
            target_price = alert.get('rhs_constant', 0)
            operator = alert.get('operator', '')
            
            # Get previous price from history
            previous_price = None
            if symbol in alert_previous_prices:
                previous_price = alert_previous_prices[symbol]
            
            # Check if price has crossed the level
            crossing_info = check_price_touch_level(current_price, target_price, operator, previous_price)
            
            # Update price history for next comparison
            alert_previous_prices[symbol] = current_price
            
            # Add current price, instrument info, and crossing information to alert
            alert['current_price'] = current_price
            alert['instrument_type'] = get_instrument_type(symbol)
            alert['crossing_info'] = crossing_info
            
            alerts_with_prices.append(alert)
        
        # Update the response with enhanced alert data
        alerts_data['data'] = alerts_with_prices
        
        return jsonify({'alerts': alerts_data, 'success': True}), 200
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error in get_alert_prices: {error_msg}")
        
        # Check if it's a token error
        if "TokenException" in error_msg or "Incorrect" in error_msg:
            return jsonify({'error': 'Authentication failed. Please login again.', 'success': False}), 401
        else:
            return jsonify({'error': f'Error fetching alert prices: {error_msg}', 'success': False}), 500

# Debug auth route moved to app/auth/routes.py (auth.debug)

@app.route('/levels/save', methods=['POST'])
def save_level_endpoint():
    """API endpoint to save a level (supports dynamic levels)"""
    try:
        data = request.get_json()
        index_type = data.get('index_type')  # 'BANK_NIFTY' or 'NIFTY_50'
        level_value = data.get('level_value')
        level_uuid = data.get('uuid')  # Optional: for updating existing level
        
        if not all([index_type, level_value]):
            return jsonify({'error': 'Missing required fields (index_type, level_value)', 'success': False}), 400
        
        if index_type not in ['BANK_NIFTY', 'NIFTY_50']:
            return jsonify({'error': 'Invalid index_type. Must be BANK_NIFTY or NIFTY_50', 'success': False}), 400
        
        if not isinstance(level_value, (int, float)) or level_value <= 0:
            return jsonify({'error': 'level_value must be a positive number', 'success': False}), 400
        
        # Use a default user_id for now (you can modify this based on your auth system)
        user_id = 'default_user'
        
        result_uuid = save_level(user_id, index_type, level_value, level_uuid)
        
        if result_uuid:
            return jsonify({
                'message': 'Level saved successfully', 
                'success': True, 
                'uuid': result_uuid
            }), 200
        else:
            return jsonify({'error': 'Failed to save level', 'success': False}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error saving level: {str(e)}', 'success': False}), 500

@app.route('/levels/get', methods=['GET'])
def get_levels_endpoint():
    """API endpoint to get all levels"""
    try:
        # Use a default user_id for now (you can modify this based on your auth system)
        user_id = 'default_user'
        index_type = request.args.get('index_type')  # Optional filter
        today_only = request.args.get('today_only', 'false').lower() == 'true'  # Optional filter for today's levels only
        
        levels = get_levels(user_id, index_type, today_only)
        print(f"Returning levels: BANK_NIFTY={len(levels['BANK_NIFTY'])}, NIFTY_50={len(levels['NIFTY_50'])}")
        return jsonify({'levels': levels, 'success': True}), 200
        
    except Exception as e:
        print(f"Error in get_levels_endpoint: {e}")
        return jsonify({'error': f'Error getting levels: {str(e)}', 'success': False}), 500

@app.route('/levels/clear', methods=['POST'])
def clear_levels_endpoint():
    """API endpoint to clear levels (for daily refresh)"""
    try:
        data = request.get_json() or {}
        index_type = data.get('index_type')  # Optional: clear specific index type
        clear_today_only = data.get('today_only', False)  # If True, only clear today's levels
        
        user_id = 'default_user'
        
        if clear_today_only:
            deleted_count = clear_levels_for_today(user_id)
        else:
            deleted_count = clear_all_levels(user_id, index_type)
        
        return jsonify({
            'message': f'Cleared {deleted_count} level(s)', 
            'success': True,
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error clearing levels: {str(e)}', 'success': False}), 500

@app.route('/levels/delete/<uuid>', methods=['DELETE'])
def delete_level_endpoint(uuid):
    """API endpoint to delete a level by UUID"""
    try:
        import sqlite3
        conn = sqlite3.connect(services.DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if level exists
        cursor.execute('SELECT uuid FROM level WHERE uuid = ?', (uuid,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Level not found', 'success': False}), 404
        
        # Delete the level
        cursor.execute('DELETE FROM level WHERE uuid = ?', (uuid,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Level deleted successfully', 'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error deleting level: {str(e)}', 'success': False}), 500

# Session and Zerodha routes moved to app/auth/routes.py

# ============================================================================
# Trading/Trend Detection API Endpoints
# ============================================================================

@app.route('/trading/set-entry-price', methods=['POST'])
def set_entry_price():
    """API endpoint to set entry price for an instrument (saves to DB and updates cache)"""
    try:
        from services import save_entry_price_to_db
        
        data = request.get_json()
        instrument = data.get('instrument')  # 'NIFTY_50' or 'NIFTY_BANK'
        entry_price = data.get('entry_price')
        
        if not instrument or entry_price is None:
            return jsonify({'error': 'Missing required fields (instrument, entry_price)', 'success': False}), 400
        
        if instrument not in ['NIFTY_50', 'NIFTY_BANK']:
            return jsonify({'error': 'Invalid instrument. Must be NIFTY_50 or NIFTY_BANK', 'success': False}), 400
        
        if not isinstance(entry_price, (int, float)) or entry_price <= 0:
            return jsonify({'error': 'entry_price must be a positive number', 'success': False}), 400
        
        # Save to database (this also updates the cache automatically)
        user_id = 'default_user'  # You can modify this based on your auth system
        success = save_entry_price_to_db(user_id, instrument, float(entry_price))
        
        if success:
            return jsonify({
                'message': f'Entry price saved for {instrument}',
                'entry_price': entry_price,
                'success': True
            }), 200
        else:
            return jsonify({'error': 'Failed to save entry price to database', 'success': False}), 500
        
    except Exception as e:
        return jsonify({'error': f'Error setting entry price: {str(e)}', 'success': False}), 500

@app.route('/trading/get-trend', methods=['GET'])
def get_trend_status():
    """API endpoint to get current trend status for instruments"""
    try:
        from services import get_trend, nifty_prices, bank_nifty_prices, entry_prices_cache, previous_trends
        
        nifty_trend = get_trend(nifty_prices)
        bank_nifty_trend = get_trend(bank_nifty_prices)
        
        return jsonify({
            'trends': {
                'NIFTY_50': {
                    'trend': nifty_trend,
                    'previous_trend': previous_trends.get('NIFTY_50'),
                    'price_count': len(nifty_prices),
                    'entry_price': entry_prices_cache.get('NIFTY_50'),
                    'current_price': list(nifty_prices)[-1] if nifty_prices else None
                },
                'NIFTY_BANK': {
                    'trend': bank_nifty_trend,
                    'previous_trend': previous_trends.get('NIFTY_BANK'),
                    'price_count': len(bank_nifty_prices),
                    'entry_price': entry_prices_cache.get('NIFTY_BANK'),
                    'current_price': list(bank_nifty_prices)[-1] if bank_nifty_prices else None
                }
            },
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error getting trend status: {str(e)}', 'success': False}), 500

@app.route('/trading/get-trades', methods=['GET'])
def get_trades_endpoint():
    """API endpoint to get all live trades"""
    try:
        from services import get_trades, check_and_update_trades_from_orders, kite, PAPER_TRADING_ENABLED
        
        # Check and update trades from recent orders (only for live trading)
        if kite and not PAPER_TRADING_ENABLED:
            check_and_update_trades_from_orders(kite)
        
        # Get status filter from query params
        status = request.args.get('status')  # 'OPEN' or 'CLOSED'
        instrument = request.args.get('instrument')  # 'NIFTY_50' or 'NIFTY_BANK'
        
        trades = get_trades(status=status, instrument=instrument)
        
        return jsonify({
            'trades': trades,
            'count': len(trades),
            'paper_trading': PAPER_TRADING_ENABLED,
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error getting trades: {str(e)}', 'success': False}), 500

@app.route('/trading/get-paper-trades', methods=['GET'])
def get_paper_trades_endpoint():
    """API endpoint to get all paper trades"""
    try:
        from services import get_paper_trades
        
        # Get filters from query params
        status = request.args.get('status')  # 'OPEN' or 'CLOSED'
        instrument = request.args.get('instrument')  # 'NIFTY_50' or 'NIFTY_BANK'
        date_filter = request.args.get('date')  # 'YYYY-MM-DD' format, defaults to today if None
        
        trades = get_paper_trades(status=status, instrument=instrument, date_filter=date_filter)
        
        return jsonify({
            'trades': trades,
            'count': len(trades),
            'date_filter': date_filter or datetime.now().date().isoformat(),
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error getting paper trades: {str(e)}', 'success': False}), 500

@app.route('/trading/update-trades', methods=['POST'])
def update_trades_endpoint():
    """API endpoint to manually trigger trade status update from orders"""
    try:
        from services import check_and_update_trades_from_orders, kite
        
        if not kite:
            return jsonify({'error': 'KiteConnect not initialized', 'success': False}), 400
        
        updated_count = check_and_update_trades_from_orders(kite)
        
        return jsonify({
            'message': f'Updated {updated_count} trades',
            'updated_count': updated_count,
            'success': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error updating trades: {str(e)}', 'success': False}), 500

# ============================================================================
# SocketIO Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    from flask import request
    print(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected'})
    
    # Don't start WebSocket here - it should already be running from server startup
    # Starting it here could cause Twisted reactor conflicts
    if not continuous_websocket_running:
        print("Warning: Continuous WebSocket not running. It should start on server startup.")
    
    # Send current prices if available
    if websocket_prices['NIFTY 50']['last_price'] > 0 or websocket_prices['NIFTY BANK']['last_price'] > 0:
        try:
            global kite
            if kite:
                nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
                bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
                
                # Calculate change and change_percent using previous_close from WebSocket if available
                nifty_current = websocket_prices['NIFTY 50']['last_price'] or nifty_data.get('last_price', 0)
                nifty_previous = websocket_prices['NIFTY 50'].get('previous_close', 0) or nifty_data.get('ohlc', {}).get('close', 0)
                nifty_change = nifty_data.get('net_change', 0)
                if nifty_previous > 0 and nifty_current > 0:
                    nifty_change = nifty_current - nifty_previous
                    nifty_change_percent = (nifty_change / nifty_previous) * 100
                else:
                    nifty_change_percent = nifty_data.get('net_change', 0) / nifty_data.get('ohlc', {}).get('close', 1) * 100 if nifty_data.get('ohlc', {}).get('close') else 0
                
                bank_nifty_current = websocket_prices['NIFTY BANK']['last_price'] or bank_nifty_data.get('last_price', 0)
                bank_nifty_previous = websocket_prices['NIFTY BANK'].get('previous_close', 0) or bank_nifty_data.get('ohlc', {}).get('close', 0)
                bank_nifty_change = bank_nifty_data.get('net_change', 0)
                if bank_nifty_previous > 0 and bank_nifty_current > 0:
                    bank_nifty_change = bank_nifty_current - bank_nifty_previous
                    bank_nifty_change_percent = (bank_nifty_change / bank_nifty_previous) * 100
                else:
                    bank_nifty_change_percent = bank_nifty_data.get('net_change', 0) / bank_nifty_data.get('ohlc', {}).get('close', 1) * 100 if bank_nifty_data.get('ohlc', {}).get('close') else 0
                
                current_prices = {
                    'nifty': {
                        'name': 'NIFTY 50',
                        'current_price': nifty_current,
                        'change': nifty_change,
                        'change_percent': nifty_change_percent,
                        'previous_close': nifty_previous,
                        'last_updated': websocket_prices['NIFTY 50']['timestamp'] or nifty_data.get('timestamp', 'N/A')
                    },
                    'bank_nifty': {
                        'name': 'NIFTY BANK',
                        'current_price': bank_nifty_current,
                        'change': bank_nifty_change,
                        'change_percent': bank_nifty_change_percent,
                        'previous_close': bank_nifty_previous,
                        'last_updated': websocket_prices['NIFTY BANK']['timestamp'] or bank_nifty_data.get('timestamp', 'N/A')
                    }
                }
                emit('price_update', current_prices)
        except Exception as e:
            print(f"Error sending initial prices: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    from flask import request
    print(f"Client disconnected: {request.sid}")

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500

# ============================================================================
# Main Execution
# ============================================================================

if __name__ == '__main__':
    import os
    import sys
    
    # Check if we're running in debug mode from UI
    is_debugging = (
        '--debug' in sys.argv or 
        'debug' in os.environ.get('FLASK_ENV', '').lower() or
        'PYTHONPATH' in os.environ or  # VS Code debugger sets this
        'DEBUGPY' in os.environ or     # VS Code Python debugger
        len(sys.argv) > 1 and any('debug' in arg.lower() for arg in sys.argv)
    )
    
    port = 5001
    
    # Set environment variables to prevent multiple processes during debugging
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Disable Flask's auto-reloader when debugging to prevent multiple instances
    use_reloader = not is_debugging
    
    print(f"🚀 Starting Flask app on port {port}")
    print("📊 Levels database storage enabled")
    print("🔌 Continuous WebSocket streaming enabled")
    print(f"🔧 Debug mode: {'ON' if is_debugging else 'OFF'}")
    print(f"🔄 Auto-reloader: {'OFF' if not use_reloader else 'ON'}")
    
    # Verify auth blueprint is registered
    try:
        if 'auth' in [bp.name for bp in app.blueprints.values()]:
            print("✓ Authentication module loaded")
        else:
            print("⚠ Authentication module not loaded - using fallback")
    except Exception as e:
        print(f"⚠ Could not verify auth blueprint: {e}")
    
    # Start continuous WebSocket connection in background
    # Only start once to avoid Twisted reactor conflicts
    def start_websocket_on_startup():
        time.sleep(3)  # Wait for server to fully start
        try:
            if not continuous_websocket_running and continuous_kws is None:
                print("Starting continuous WebSocket on server startup...")
                start_continuous_websocket()
            else:
                print("Continuous WebSocket already running or initialized")
        except Exception as e:
            print(f"Error starting continuous WebSocket on startup: {e}")
    
    # Only start the thread if not already running
    if not continuous_websocket_running:
        threading.Thread(target=start_websocket_on_startup, daemon=True).start()
    
    # Start trend monitoring background thread
    from services import start_trend_monitoring, start_paper_trade_monitoring, PAPER_TRADING_ENABLED
    start_trend_monitoring()
    
    # Start paper trade monitoring background thread if paper trading is enabled
    if PAPER_TRADING_ENABLED:
        start_paper_trade_monitoring()
        print("📝 Paper trading mode: ENABLED")
    else:
        print("💰 Live trading mode: ENABLED")
    
    # Run with SocketIO (supports WebSocket)
    try:
        socketio.run(
            app,
            debug=True,
            host='0.0.0.0',
            port=port,
            use_reloader=use_reloader,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n✓ Server stopped by user")
    except Exception as e:
        print(f"\n✗ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
