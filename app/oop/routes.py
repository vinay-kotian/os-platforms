"""
Routes for Order Orchestrator Platform (OOP).
"""
from flask import Blueprint, request, jsonify, render_template, session
from app.auth.middleware import login_required
from app.oop.oop_service import get_oop_service
from app.tre.tre_service import TREService
from app.database.models import Database

oop_bp = Blueprint('oop', __name__, url_prefix='/oop')


@oop_bp.route('/')
@login_required
def index():
    """OOP orders and trades page."""
    user_id = session.get('user_id')
    oop_service = get_oop_service()
    db = Database()
    
    # Get OOP settings
    oop_settings = db.get_oop_settings(user_id)
    
    # Get orders
    orders = oop_service.get_user_orders(user_id)
    
    # Get trades
    trades = oop_service.get_user_trades(user_id, limit=50)
    
    # Get pending trade signals
    tre_service = TREService(user_id)
    pending_signals = tre_service.get_user_trade_signals(user_id, status='pending')
    
    # Check Zerodha authentication status
    from app.prices.zerodha_service import ZerodhaService
    zerodha = ZerodhaService()
    zerodha_authenticated = zerodha.is_authenticated(user_id)
    
    return render_template('oop/index.html',
                         orders=orders,
                         trades=trades,
                         pending_signals=pending_signals,
                         oop_settings=oop_settings,
                         zerodha_authenticated=zerodha_authenticated)


@oop_bp.route('/api/create-order', methods=['POST'])
@login_required
def create_order():
    """API endpoint to create order from trade signal."""
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data or 'trade_signal_id' not in data:
        return jsonify({'success': False, 'error': 'trade_signal_id is required'}), 400
    
    trade_signal_id = data['trade_signal_id']
    
    # Verify signal belongs to user
    tre_service = TREService(user_id)
    signals = tre_service.get_user_trade_signals(user_id, status='pending')
    signal = None
    for s in signals:
        if s['trade_signal_id'] == trade_signal_id:
            signal = s
            break
    
    if not signal:
        return jsonify({'success': False, 'error': 'Trade signal not found or already processed'}), 404
    
    # Create order
    oop_service = get_oop_service()
    success, order_id, error = oop_service.create_order_from_signal(trade_signal_id)
    
    if success:
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Order created successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to create order'
        }), 400


@oop_bp.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    """API endpoint to get orders."""
    user_id = session.get('user_id')
    status = request.args.get('status')  # Optional filter
    
    oop_service = get_oop_service()
    orders = oop_service.get_user_orders(user_id, status=status)
    
    return jsonify({
        'success': True,
        'orders': orders,
        'count': len(orders)
    })


@oop_bp.route('/api/trades', methods=['GET'])
@login_required
def get_trades():
    """API endpoint to get trades."""
    user_id = session.get('user_id')
    limit = request.args.get('limit', type=int)  # Optional limit
    
    oop_service = get_oop_service()
    trades = oop_service.get_user_trades(user_id, limit=limit)
    
    return jsonify({
        'success': True,
        'trades': trades,
        'count': len(trades)
    })


@oop_bp.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """API endpoint to cancel an order."""
    user_id = session.get('user_id')
    
    # Verify order belongs to user
    oop_service = get_oop_service()
    orders = oop_service.get_user_orders(user_id)
    order = None
    for o in orders:
        if o['order_id'] == order_id:
            order = o
            break
    
    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404
    
    if order['status'] not in ['pending', 'active']:
        return jsonify({'success': False, 'error': 'Order cannot be cancelled'}), 400
    
    # Cancel order
    db = Database()
    success = db.update_oop_order_status(order_id, 'cancelled')
    
    if success:
        return jsonify({'success': True, 'message': 'Order cancelled'})
    else:
        return jsonify({'success': False, 'error': 'Failed to cancel order'}), 500


@oop_bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """API endpoint to update OOP settings."""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User not authenticated'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400
    
    paper_trading = data.get('paper_trading', True)
    is_active = data.get('is_active', True)
    
    # Update settings
    db = Database()
    success = db.create_or_update_oop_settings(
        user_id=user_id,
        paper_trading=paper_trading,
        is_active=is_active
    )
    
    if success:
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to update settings'}), 500

