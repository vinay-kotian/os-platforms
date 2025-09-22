import os
import json
import requests
import sqlite3
from datetime import datetime
from flask import Flask, redirect, request, session, url_for, render_template, flash
from flask.json import jsonify
from kiteconnect import KiteConnect
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = "thisisasecretkey"   # needed for session handling

# File to store persistent session data
SESSION_FILE = 'session_data.json'

# Database file
DATABASE_FILE = 'app.db'

# Global variables to store user's API credentials
user_api_key = None
user_api_secret = None
kite = None

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
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing database: {e}")

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

# Initialize database and load existing session on startup
init_database()
load_session_data()

@app.before_request
def before_request():
    """Sync session from file before each request"""
    if not session.get('access_token') and os.path.exists(SESSION_FILE):
        sync_session_from_file()

@app.route('/')
def index():
    """Home page - redirect based on login status"""
    # Check if user is logged in (has access token and kite instance)
    if session.get('access_token') and kite:
        # User is logged in, redirect to prices page
        return redirect(url_for('prices'))
    else:
        # User is not logged in, show login page
        return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for Zerodha API credentials"""
    global user_api_key, user_api_secret, kite
    
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        
        if not api_key or not api_secret:
            flash('Please enter both API Key and API Secret', 'error')
            return render_template('login.html')
        
        try:
            # Store user credentials
            user_api_key = api_key
            user_api_secret = api_secret
            
            # Initialize KiteConnect with user's API key
            kite = KiteConnect(api_key=api_key)
            
            # Generate login URL
            login_url = kite.login_url()
            
            # Store in session for callback
            session['api_key'] = api_key
            session['api_secret'] = api_secret
            
            flash('Credentials saved! Please complete the login process.', 'success')
            return render_template('login.html', login_url=login_url, api_key=api_key)
            
        except Exception as e:
            flash(f'Error initializing KiteConnect: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/callback')
def login_callback():
    """Handle Zerodha login callback"""
    global kite
    
    request_token = request.args.get("request_token")
    if not request_token:
        flash('Error: No request token received', 'error')
        return redirect(url_for('login'))
    
    try:
        # Get stored credentials from session
        api_key = session.get('api_key')
        api_secret = session.get('api_secret')
        
        if not api_key or not api_secret:
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('login'))
        
        # Initialize KiteConnect with stored credentials
        kite = KiteConnect(api_key=api_key)
        
        # Generate session to get access_token
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        
        # Save access token in session
        session["access_token"] = access_token
        kite.set_access_token(access_token)
        
        # Save to file for persistence
        save_session_data()
        
        flash('Login successful! You can now access stock data.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'Login failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/prices')
def prices():
    """Nifty and Bank Nifty prices page"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        flash('Please login to view live stock prices', 'error')
        return redirect(url_for('login'))
    
    try:
        # Fetch live prices
        nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
        bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
        
        # Format the data
        prices_data = {
            'nifty': {
                'name': nifty_data.get('tradingsymbol', 'N/A'),
                'current_price': nifty_data.get('last_price', 0),
                'change': nifty_data.get('net_change', 0),
                'change_percent': nifty_data.get('net_change', 0) / nifty_data.get('ohlc').get('close', 0) * 100,
                'last_updated': nifty_data.get('timestamp', 'N/A')
            },
            'bank_nifty': {
                'name': bank_nifty_data.get('tradingsymbol', 'N/A'),
                'current_price': bank_nifty_data.get('last_price', 0),
                'change': bank_nifty_data.get('net_change', 0),
                'change_percent': bank_nifty_data.get('net_change', 0) / nifty_data.get('ohlc').get('close', 0) * 100,
                'last_updated': bank_nifty_data.get('timestamp', 'N/A')
            }
        }
        
        return render_template('prices.html', prices=prices_data)
        
    except Exception as e:
        flash(f'Error fetching stock prices: {str(e)}', 'error')
        return render_template('prices.html', prices=None)

@app.route('/stocks/fetch-price')
def fetch_prices():
    """API endpoint to fetch current stock prices"""
    global kite
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Fetch live prices using the same logic as the main prices page
        nifty_data = kite.quote("NSE:NIFTY 50").get('NSE:NIFTY 50', {})
        bank_nifty_data = kite.quote("NSE:NIFTY BANK").get('NSE:NIFTY BANK', {})
        
        # Format the data to match the template structure
        prices_data = {
            'nifty': {
                'name': nifty_data.get('tradingsymbol', 'N/A'),
                'current_price': nifty_data.get('last_price', 0),
                'change': nifty_data.get('net_change', 0),
                'change_percent': nifty_data.get('net_change', 0) / nifty_data.get('ohlc', {}).get('close', 1) * 100 if nifty_data.get('ohlc', {}).get('close') else 0,
                'last_updated': nifty_data.get('timestamp', 'N/A')
            },
            'bank_nifty': {
                'name': bank_nifty_data.get('tradingsymbol', 'N/A'),
                'current_price': bank_nifty_data.get('last_price', 0),
                'change': bank_nifty_data.get('net_change', 0),
                'change_percent': bank_nifty_data.get('net_change', 0) / bank_nifty_data.get('ohlc', {}).get('close', 1) * 100 if bank_nifty_data.get('ohlc', {}).get('close') else 0,
                'last_updated': bank_nifty_data.get('timestamp', 'N/A')
            }
        }
        
        return jsonify(prices_data)
        
    except Exception as e:
        return jsonify({'error': f'Error fetching stock prices: {str(e)}'}), 500

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
        conn = sqlite3.connect(DATABASE_FILE)
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
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Get API credentials from session
        api_key = session.get('api_key')
        access_token = session.get('access_token')
        
        # Prepare headers
        headers = {
            'X-Kite-Version': '3',
            'Authorization': f'token {api_key}:{access_token}'
        }
        
        # Send DELETE request to KITE alerts API
        response = requests.delete(
            f'https://api.kite.trade/alerts/{uuid}',
            headers=headers
        )
        
        if response.status_code == 200:
            # Also delete from local database
            delete_alert_from_database(uuid)
            return jsonify({'message': 'Alert deleted successfully', 'success': True}), 200
        else:
            return jsonify({'error': f'Failed to delete alert: {response.text}', 'success': False}), 500
            
    except Exception as e:
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

def check_alert_triggers():
    """Check if any stored alerts should be triggered based on current prices"""
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

@app.route('/session/status')
def session_status():
    """Debug endpoint to check session status"""
    return jsonify({
        'session_data': {
            'api_key': session.get('api_key'),
            'access_token': '***' if session.get('access_token') else None,
            'session_keys': list(session.keys())
        },
        'global_data': {
            'user_api_key': user_api_key,
            'kite_initialized': kite is not None
        },
        'file_exists': os.path.exists(SESSION_FILE)
    })

@app.route('/logout')
def logout():
    """Logout and clear session data"""
    global user_api_key, user_api_secret, kite
    
    # Clear global variables
    user_api_key = None
    user_api_secret = None
    kite = None
    
    # Clear session
    session.clear()
    
    # Remove session file
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
