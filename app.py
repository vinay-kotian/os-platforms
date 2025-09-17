import os
from flask import Flask, redirect, request, session, url_for, render_template, flash
from flask.json import jsonify
from kiteconnect import KiteConnect
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = "thisisasecretkey"   # needed for session handling

# Global variables to store user's API credentials
user_api_key = None
user_api_secret = None
kite = None

@app.route('/')
def index():
    """Home page"""
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
    prices = {
        'NIFTY50': kite.ltp("NSE:NIFTY 50").get('NSE:NIFTY 50').get('last_price'),
        'BANKNIFTY': kite.ltp("NSE:NIFTY BANK").get('NSE:NIFTY BANK').get('last_price')
    }  
    return jsonify(prices)

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
