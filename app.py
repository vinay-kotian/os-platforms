import os
import json
import requests
import sqlite3
import uuid
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
        
        # Create three_levels table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS three_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                index_type TEXT NOT NULL,  -- 'BANK_NIFTY' or 'NIFTY_50'
                level_number INTEGER NOT NULL,  -- 1, 2, or 3
                level_value REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, index_type, level_number)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("Database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing database: {e}")

def save_three_level(user_id, index_type, level_number, level_value):
    """Save a three level to the database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        # Check if level already exists to get existing UUID or create new one
        cursor.execute('''
            SELECT uuid FROM three_levels 
            WHERE user_id = ? AND index_type = ? AND level_number = ?
        ''', (user_id, index_type, level_number))
        
        existing_level = cursor.fetchone()
        level_uuid = existing_level[0] if existing_level else str(uuid.uuid4())
        
        # Insert or update the level with UUID
        cursor.execute('''
            INSERT OR REPLACE INTO three_levels 
            (uuid, user_id, index_type, level_number, level_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (level_uuid, user_id, index_type, level_number, level_value, current_time, current_time))
        
        conn.commit()
        conn.close()
        print(f"Three level saved with UUID: {level_uuid}")
        return True
    except Exception as e:
        print(f"Error saving three level: {e}")
        return False

def get_three_levels(user_id):
    """Get all three levels for a user"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uuid, index_type, level_number, level_value, updated_at
            FROM three_levels 
            WHERE user_id = ?
            ORDER BY index_type, level_number
        ''', (user_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert to dictionary format
        levels = {
            'BANK_NIFTY': {1: None, 2: None, 3: None},
            'NIFTY_50': {1: None, 2: None, 3: None}
        }
        
        for row in results:
            level_uuid, index_type, level_number, level_value, updated_at = row
            levels[index_type][level_number] = {
                'uuid': level_uuid,
                'value': level_value,
                'updated_at': updated_at
            }
        
        return levels
    except Exception as e:
        print(f"Error getting three levels: {e}")
        return {
            'BANK_NIFTY': {1: None, 2: None, 3: None},
            'NIFTY_50': {1: None, 2: None, 3: None}
        }

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
    
    print(f"Delete alert request for UUID: {uuid}")
    
    # Check if user is logged in
    if not session.get('access_token') or not kite:
        print("Delete failed: Not authenticated")
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
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

# Simple in-memory price history for tracking crossings (in production, use Redis or database)
price_history = {}

@app.route('/alerts/prices', methods=['GET'])
def get_alert_prices():
    """API endpoint to get current prices for all alerts with crossing detection"""
    global kite, price_history
    
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
            if symbol in price_history:
                previous_price = price_history[symbol]
            
            # Check if price has crossed the level
            crossing_info = check_price_touch_level(current_price, target_price, operator, previous_price)
            
            # Update price history for next comparison
            price_history[symbol] = current_price
            
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

@app.route('/debug/auth', methods=['GET'])
def debug_auth():
    """Debug endpoint to check authentication status"""
    global kite
    
    debug_info = {
        'session_access_token': bool(session.get('access_token')),
        'session_api_key': bool(session.get('api_key')),
        'global_kite_initialized': kite is not None,
        'global_api_key': user_api_key is not None,
        'session_file_exists': os.path.exists(SESSION_FILE)
    }
    
    if kite:
        try:
            # Test if kite object is working
            profile = kite.profile()
            debug_info['kite_profile'] = profile.get('user_name', 'Unknown')
            debug_info['kite_status'] = 'working'
        except Exception as e:
            debug_info['kite_error'] = str(e)
            debug_info['kite_status'] = 'error'
    
        return jsonify(debug_info)

@app.route('/three-levels/save', methods=['POST'])
def save_three_level_endpoint():
    """API endpoint to save a three level"""
    try:
        data = request.get_json()
        index_type = data.get('index_type')  # 'BANK_NIFTY' or 'NIFTY_50'
        level_number = data.get('level_number')  # 1, 2, or 3
        level_value = data.get('level_value')
        
        if not all([index_type, level_number, level_value]):
            return jsonify({'error': 'Missing required fields', 'success': False}), 400
        
        if index_type not in ['BANK_NIFTY', 'NIFTY_50']:
            return jsonify({'error': 'Invalid index_type', 'success': False}), 400
        
        if level_number not in [1, 2, 3]:
            return jsonify({'error': 'Invalid level_number', 'success': False}), 400
        
        # Use a default user_id for now (you can modify this based on your auth system)
        user_id = 'default_user'
        
        success = save_three_level(user_id, index_type, level_number, level_value)
        
        if success:
            # Get the UUID of the saved level
            try:
                conn = sqlite3.connect(DATABASE_FILE)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT uuid FROM three_levels 
                    WHERE user_id = ? AND index_type = ? AND level_number = ?
                ''', (user_id, index_type, level_number))
                result = cursor.fetchone()
                conn.close()
                
                level_uuid = result[0] if result else None
                return jsonify({
                    'message': 'Level saved successfully', 
                    'success': True, 
                    'uuid': level_uuid
                }), 200
            except Exception as e:
                return jsonify({
                    'message': 'Level saved successfully', 
                    'success': True
                }), 200
        else:
            return jsonify({'error': 'Failed to save level', 'success': False}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error saving level: {str(e)}', 'success': False}), 500

@app.route('/three-levels/get', methods=['GET'])
def get_three_levels_endpoint():
    """API endpoint to get all three levels"""
    try:
        # Use a default user_id for now (you can modify this based on your auth system)
        user_id = 'default_user'
        
        levels = get_three_levels(user_id)
        return jsonify({'levels': levels, 'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error getting levels: {str(e)}', 'success': False}), 500

@app.route('/three-levels/get/<uuid>', methods=['GET'])
def get_three_level_by_uuid_endpoint(level_uuid):
    """API endpoint to get a specific three level by UUID"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT uuid, user_id, index_type, level_number, level_value, created_at, updated_at
            FROM three_levels 
            WHERE uuid = ?
        ''', (level_uuid,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            level_uuid, user_id, index_type, level_number, level_value, created_at, updated_at = result
            return jsonify({
                'level': {
                    'uuid': level_uuid,
                    'user_id': user_id,
                    'index_type': index_type,
                    'level_number': level_number,
                    'level_value': level_value,
                    'created_at': created_at,
                    'updated_at': updated_at
                },
                'success': True
            }), 200
        else:
            return jsonify({'error': 'Level not found', 'success': False}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error getting level: {str(e)}', 'success': False}), 500

@app.route('/three-levels/delete/<uuid>', methods=['DELETE'])
def delete_three_level_endpoint(level_uuid):
    """API endpoint to delete a three level by UUID"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if level exists
        cursor.execute('SELECT uuid FROM three_levels WHERE uuid = ?', (level_uuid,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Level not found', 'success': False}), 404
        
        # Delete the level
        cursor.execute('DELETE FROM three_levels WHERE uuid = ?', (level_uuid,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Level deleted successfully', 'success': True}), 200
        
    except Exception as e:
        return jsonify({'error': f'Error deleting level: {str(e)}', 'success': False}), 500

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
    
    port = 5002
    
    # Set environment variables to prevent multiple processes during debugging
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Disable Flask's auto-reloader when debugging to prevent multiple instances
    use_reloader = not is_debugging
    
    print(f"🚀 Starting Flask app on port {port}")
    print("📊 Three levels database storage enabled")
    print(f"🔧 Debug mode: {'ON' if is_debugging else 'OFF'}")
    print(f"🔄 Auto-reloader: {'OFF' if not use_reloader else 'ON'}")
    
    # Run with settings optimized for debugging
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=port,
        use_reloader=use_reloader,  # Disable reloader when debugging to prevent multiple instances
        threaded=True,
        processes=1  # Force single process
    )
