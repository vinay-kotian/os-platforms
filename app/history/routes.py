"""
Routes for historical candle data.
"""
from flask import Blueprint, request, jsonify, render_template, session
from app.auth.middleware import login_required
from app.history.history_service import HistoryService
from app.prices.zerodha_service import ZerodhaService

history_bp = Blueprint('history', __name__, url_prefix='/history')


@history_bp.route('/')
@login_required
def index():
    """History page - display historical candle data."""
    user_id = session.get('user_id')
    zerodha = ZerodhaService()
    
    # Check Zerodha login status
    zerodha_authenticated = zerodha.is_authenticated(user_id)
    zerodha_configured = zerodha.is_configured()
    
    # Get user subscriptions for dropdown
    from app.prices.price_service import PriceService
    price_service = PriceService(user_id)
    subscriptions = price_service.get_user_subscriptions(user_id)
    
    return render_template('history/index.html',
                         subscriptions=subscriptions,
                         zerodha_authenticated=zerodha_authenticated,
                         zerodha_configured=zerodha_configured)


@history_bp.route('/api/fetch', methods=['POST'])
@login_required
def fetch_historical_data():
    """API endpoint to fetch historical candle data."""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User not authenticated'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400
    
    exchange = data.get('exchange')
    symbol = data.get('symbol')
    interval = data.get('interval', 'day')
    from_date = data.get('from_date')
    to_date = data.get('to_date')
    continuous = data.get('continuous', False)
    oi = data.get('oi', False)
    
    # Validate required fields
    if not exchange or not symbol:
        return jsonify({'success': False, 'error': 'exchange and symbol are required'}), 400
    
    # If dates not provided, use default (last 30 days)
    if not from_date or not to_date:
        from datetime import datetime, timedelta
        to_date = datetime.now()
        from_date = to_date - timedelta(days=30)
        from_date = from_date.strftime('%Y-%m-%d %H:%M:%S')
        to_date = to_date.strftime('%Y-%m-%d %H:%M:%S')
    
    # Create history service
    history_service = HistoryService(user_id)
    
    # Fetch historical data
    success, candles, error = history_service.get_historical_data(
        exchange=exchange,
        symbol=symbol,
        interval=interval,
        from_date=from_date,
        to_date=to_date,
        continuous=continuous,
        oi=oi
    )
    
    if success:
        return jsonify({
            'success': True,
            'candles': candles,
            'count': len(candles) if candles else 0
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to fetch historical data'
        }), 400

