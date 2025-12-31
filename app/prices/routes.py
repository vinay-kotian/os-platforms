"""
Routes for the prices module.
"""
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from flask_socketio import emit, disconnect
from datetime import datetime
from app.database.models import Database
from app.prices.price_service import PriceService
from app.prices.zerodha_service import ZerodhaService
from app.prices.websocket_service import WebSocketService
from app.auth.middleware import login_required, admin_required


prices_bp = Blueprint('prices', __name__, url_prefix='/prices')


@prices_bp.route('/')
@login_required
def index():
    """Prices landing page - main page for logged-in users."""
    user_id = session.get('user_id')
    price_service = PriceService(user_id)
    zerodha = ZerodhaService()
    websocket_service = WebSocketService()
    
    # Get user subscriptions
    subscriptions = price_service.get_user_subscriptions(user_id)
    
    # Get current prices for subscriptions (initial load)
    prices = price_service.get_subscription_prices(user_id)
    
    # Check Zerodha login status
    zerodha_authenticated = zerodha.is_authenticated(user_id)
    zerodha_configured = zerodha.is_configured()
    
    # Initialize websocket subscriptions if authenticated
    if zerodha_authenticated and subscriptions:
        try:
            price_service._update_websocket_subscriptions(user_id)
        except Exception as e:
            print(f"Error initializing websocket subscriptions: {e}")
    
    return render_template('prices/index.html', 
                         subscriptions=subscriptions,
                         prices=prices,
                         zerodha_authenticated=zerodha_authenticated,
                         zerodha_configured=zerodha_configured)


@prices_bp.route('/api/search', methods=['POST'])
@login_required
def search_instruments():
    """Search for instruments."""
    data = request.get_json()
    query = data.get('query', '').strip()
    exchange = data.get('exchange', '').strip() or None
    
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    
    zerodha = ZerodhaService()
    
    if not zerodha.is_configured():
        return jsonify({
            'error': 'Zerodha API keys not configured',
            'configured': False
        }), 503
    
    results = zerodha.search_instruments(query, exchange)
    
    return jsonify({
        'results': results,
        'configured': True
    })


@prices_bp.route('/api/subscribe', methods=['POST'])
@login_required
def subscribe():
    """Subscribe to an instrument."""
    data = request.get_json()
    exchange = data.get('exchange', '').strip().upper()
    symbol = data.get('symbol', '').strip().upper()
    
    if not exchange or not symbol:
        return jsonify({'error': 'Exchange and symbol are required'}), 400
    
    user_id = session.get('user_id')
    price_service = PriceService(user_id)
    
    success, error = price_service.subscribe(user_id, exchange, symbol)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Subscribed to {exchange}:{symbol}'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to subscribe'
        }), 400


@prices_bp.route('/api/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Unsubscribe from an instrument."""
    data = request.get_json()
    exchange = data.get('exchange', '').strip().upper()
    symbol = data.get('symbol', '').strip().upper()
    
    if not exchange or not symbol:
        return jsonify({'error': 'Exchange and symbol are required'}), 400
    
    user_id = session.get('user_id')
    price_service = PriceService(user_id)
    
    success = price_service.unsubscribe(user_id, exchange, symbol)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Unsubscribed from {exchange}:{symbol}'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Subscription not found'
        }), 404


@prices_bp.route('/api/prices', methods=['GET'])
@login_required
def get_prices():
    """Get current prices for user subscriptions."""
    user_id = session.get('user_id')
    price_service = PriceService(user_id)
    
    prices = price_service.get_subscription_prices(user_id)
    
    return jsonify({
        'prices': prices,
        'timestamp': datetime.utcnow().isoformat()
    })


# Admin routes for Zerodha keys
@prices_bp.route('/admin/zerodha-keys', methods=['GET'])
@admin_required
def manage_zerodha_keys():
    """Admin page for managing Zerodha API keys."""
    zerodha = ZerodhaService()
    keys = zerodha.db.get_zerodha_keys()
    
    return render_template('prices/zerodha_keys.html', 
                         keys=keys,
                         configured=zerodha.is_configured())


@prices_bp.route('/admin/zerodha-keys', methods=['POST'])
@admin_required
def set_zerodha_keys():
    """Set Zerodha API keys (admin only)."""
    if request.is_json:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        api_secret = data.get('api_secret', '').strip()
    else:
        api_key = request.form.get('api_key', '').strip()
        api_secret = request.form.get('api_secret', '').strip()
    
    if not api_key or not api_secret:
        error_msg = 'API key and secret are required'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(request.url)
    
    zerodha = ZerodhaService()
    success = zerodha.set_api_keys(api_key, api_secret)
    
    if success:
        success_msg = 'Zerodha API keys updated successfully'
        if request.is_json:
            return jsonify({'success': True, 'message': success_msg})
        flash(success_msg, 'success')
    else:
        error_msg = 'Failed to update API keys'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        flash(error_msg, 'error')
    
    return redirect(request.url)


# Zerodha login routes
@prices_bp.route('/zerodha/login', methods=['GET'])
@login_required
def zerodha_login():
    """Initiate Zerodha login - redirects to Zerodha OAuth page."""
    zerodha = ZerodhaService()
    
    if not zerodha.is_configured():
        flash('Zerodha API keys are not configured. Please contact administrator.', 'error')
        return redirect(url_for('prices.index'))
    
    login_url = zerodha.get_login_url()
    
    if not login_url:
        flash('Failed to generate Zerodha login URL', 'error')
        return redirect(url_for('prices.index'))
    
    return redirect(login_url)


@prices_bp.route('/zerodha/callback', methods=['GET'])
@login_required
def zerodha_callback():
    """Handle Zerodha OAuth callback and store access token."""
    request_token = request.args.get('request_token')
    status = request.args.get('status')
    action = request.args.get('action')
    
    if status == 'success' and request_token:
        zerodha = ZerodhaService()
        user_id = session.get('user_id')
        
        # Generate access token from request token
        access_token = zerodha.generate_session(request_token)
        
        if access_token:
            # Store access token in database
            db = Database()
            db.set_zerodha_session(user_id, access_token)
            
            flash('Successfully connected to Zerodha!', 'success')
        else:
            flash('Failed to generate access token. Please try again.', 'error')
    elif status == 'failure' or action == 'exit':
        flash('Zerodha login was cancelled or failed.', 'error')
    else:
        flash('Invalid callback parameters.', 'error')
    
    return redirect(url_for('prices.index'))


@prices_bp.route('/zerodha/logout', methods=['POST'])
@login_required
def zerodha_logout():
    """Logout from Zerodha (clear access token)."""
    user_id = session.get('user_id')
    db = Database()
    db.delete_zerodha_session(user_id)
    
    flash('Disconnected from Zerodha', 'info')
    return redirect(url_for('prices.index'))


# SocketIO event handlers
def register_socketio_handlers(socketio, app):
    """Register SocketIO event handlers for price updates."""
    from app.prices.websocket_service import WebSocketService
    from app.prices.price_service import PriceService
    from flask import request as flask_request
    
    websocket_service = WebSocketService()
    websocket_service.set_socketio(socketio)
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Handle client connection."""
        from flask import request, session
        import traceback
        
        try:
            # Try to access session - SocketIO should have access to Flask session
            # If session is not available, this will raise an error
            user_id = None
            try:
                user_id = session.get('user_id')
                print(f"WebSocket connect attempt - Session available, user_id: {user_id}, session keys: {list(session.keys())}")
            except Exception as session_error:
                print(f"Error accessing session in WebSocket handler: {session_error}")
                traceback.print_exc()
                # Don't reject immediately - allow connection but emit error
                emit('websocket_error', {'message': 'Session not available. Please refresh the page and try again.'})
                return True  # Allow connection but with limited functionality
            
            if not user_id:
                print(f"WebSocket connection: No user_id in session. Session keys: {list(session.keys())}")
                emit('websocket_status', {'connected': False, 'message': 'Not authenticated. Please log in.'})
                return True  # Allow connection but user won't get price updates
            
            print(f"WebSocket connection accepted for user_id: {user_id}")
            
            # Initialize websocket connection if Zerodha is authenticated
            zerodha = ZerodhaService()
            if zerodha.is_authenticated(user_id):
                try:
                    # Connect to Zerodha websocket
                    print(f"Attempting to connect Zerodha websocket for user_id: {user_id}")
                    if websocket_service.connect(user_id):
                        # Subscribe to user's instruments
                        price_service = PriceService(user_id)
                        price_service._update_websocket_subscriptions(user_id)
                        emit('websocket_status', {'connected': True, 'message': 'Connected to live prices'})
                    else:
                        # More detailed error will be sent by websocket_service
                        print(f"Failed to connect Zerodha websocket for user_id: {user_id}")
                        emit('websocket_status', {
                            'connected': False, 
                            'message': 'Failed to connect to Zerodha websocket. Check server logs for details.'
                        })
                except Exception as e:
                    error_msg = f"Error connecting websocket: {e}"
                    print(error_msg)
                    traceback.print_exc()
                    emit('websocket_error', {'message': error_msg})
            else:
                emit('websocket_status', {
                    'connected': False, 
                    'message': 'Please connect to Zerodha first. Click "Login with Zerodha" to authenticate.'
                })
            
            return True  # Allow the connection
        except Exception as e:
            print(f"Unexpected error in WebSocket connect handler: {e}")
            traceback.print_exc()
            # Allow connection but emit error
            emit('websocket_error', {'message': f'Connection error: {str(e)}'})
            return True
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        # Note: We don't disconnect the Zerodha websocket here as it may be used by other clients
        pass

