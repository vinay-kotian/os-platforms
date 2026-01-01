"""
Routes for the alerts module.
"""
from flask import Blueprint, request, jsonify, session, render_template
from datetime import datetime
from app.alerts.alert_service import AlertService
from app.auth.middleware import login_required


alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')


@alerts_bp.route('/')
@login_required
def index():
    """Alerts management page."""
    user_id = session.get('user_id')
    alert_service = AlertService(user_id)
    
    # Get user's subscriptions to show in dropdown
    from app.prices.price_service import PriceService
    price_service = PriceService(user_id)
    subscriptions = price_service.get_user_subscriptions(user_id)
    
    # Get user's level alerts
    level_alerts = alert_service.get_user_level_alerts(user_id)
    
    return render_template('alerts/index.html',
                         level_alerts=level_alerts,
                         subscriptions=subscriptions)


@alerts_bp.route('/api/create', methods=['POST'])
@login_required
def create_level_alert():
    """Create a new level alert."""
    data = request.get_json()
    user_id = session.get('user_id')
    
    exchange = data.get('exchange', '').strip().upper()
    symbol = data.get('symbol', '').strip().upper()
    price_level = data.get('price_level')
    ttl_type = data.get('ttl_type', 'intraday').strip().lower()
    expires_at = data.get('expires_at', '').strip() or None
    
    # Validation
    if not exchange or not symbol:
        return jsonify({'error': 'Exchange and symbol are required'}), 400
    
    if price_level is None or price_level <= 0:
        return jsonify({'error': 'Valid price level is required'}), 400
    
    if ttl_type not in ['intraday', 'longterm']:
        return jsonify({'error': "TTL type must be 'intraday' or 'longterm'"}), 400
    
    alert_service = AlertService(user_id)
    success, level_alert_id, error = alert_service.create_level_alert(
        user_id=user_id,
        exchange=exchange,
        symbol=symbol,
        price_level=float(price_level),
        ttl_type=ttl_type,
        expires_at=expires_at
    )
    
    if success:
        return jsonify({
            'success': True,
            'level_alert_id': level_alert_id,
            'message': 'Level alert created successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to create level alert'
        }), 400


@alerts_bp.route('/api/update/<int:level_alert_id>', methods=['PUT'])
@login_required
def update_level_alert(level_alert_id):
    """Update a level alert."""
    data = request.get_json()
    user_id = session.get('user_id')
    
    alert_service = AlertService(user_id)
    
    # Get update fields
    price_level = data.get('price_level')
    ttl_type = data.get('ttl_type', '').strip().lower() or None
    expires_at = data.get('expires_at', '').strip() or None
    is_active = data.get('is_active')
    
    # Validate ttl_type if provided
    if ttl_type and ttl_type not in ['intraday', 'longterm']:
        return jsonify({'error': "TTL type must be 'intraday' or 'longterm'"}), 400
    
    # Convert price_level to float if provided
    if price_level is not None:
        try:
            price_level = float(price_level)
            if price_level <= 0:
                return jsonify({'error': 'Price level must be greater than 0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid price level'}), 400
    
    # Convert is_active to bool if provided
    if is_active is not None:
        is_active = bool(is_active)
    
    success, error = alert_service.update_level_alert(
        level_alert_id=level_alert_id,
        user_id=user_id,
        price_level=price_level,
        ttl_type=ttl_type,
        expires_at=expires_at,
        is_active=is_active
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Level alert updated successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to update level alert'
        }), 400


@alerts_bp.route('/api/delete/<int:level_alert_id>', methods=['DELETE'])
@login_required
def delete_level_alert(level_alert_id):
    """Delete a level alert."""
    user_id = session.get('user_id')
    alert_service = AlertService(user_id)
    
    success, error = alert_service.delete_level_alert(level_alert_id, user_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Level alert deleted successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to delete level alert'
        }), 404


@alerts_bp.route('/api/list', methods=['GET'])
@login_required
def list_level_alerts():
    """Get all level alerts for the current user."""
    user_id = session.get('user_id')
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    
    alert_service = AlertService(user_id)
    level_alerts = alert_service.get_user_level_alerts(user_id, active_only=active_only)
    
    return jsonify({
        'success': True,
        'level_alerts': level_alerts
    })


@alerts_bp.route('/api/<int:level_alert_id>', methods=['GET'])
@login_required
def get_level_alert(level_alert_id):
    """Get a specific level alert."""
    user_id = session.get('user_id')
    alert_service = AlertService(user_id)
    
    level_alert = alert_service.get_level_alert(level_alert_id, user_id)
    
    if level_alert:
        return jsonify({
            'success': True,
            'level_alert': level_alert
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Level alert not found'
        }), 404

