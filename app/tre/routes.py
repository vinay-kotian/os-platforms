"""
Routes for Trade Rule Engine (TRE).
"""
from flask import Blueprint, request, jsonify, render_template, session
from app.auth.middleware import login_required
from app.tre.tre_service import TREService
from app.database.models import Database

tre_bp = Blueprint('tre', __name__, url_prefix='/tre')


@tre_bp.route('/')
@login_required
def index():
    """TRE settings page."""
    user_id = session.get('user_id')
    db = Database()
    
    # Get TRE settings
    tre_settings = db.get_tre_settings(user_id)
    
    # Get trade signals
    tre_service = TREService(user_id)
    trade_signals = tre_service.get_user_trade_signals(user_id)
    
    return render_template('tre/index.html',
                         tre_settings=tre_settings,
                         trade_signals=trade_signals)


@tre_bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """API endpoint to update TRE settings."""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'User not authenticated'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400
    
    stop_loss_percent = data.get('stop_loss_percent', 2.0)
    target_percent = data.get('target_percent', 5.0)
    trend_lookback_minutes = data.get('trend_lookback_minutes', 20)
    is_active = data.get('is_active', True)
    
    # Validate inputs
    if stop_loss_percent < 0 or stop_loss_percent > 100:
        return jsonify({'success': False, 'error': 'Stop loss must be between 0 and 100'}), 400
    
    if target_percent < 0 or target_percent > 100:
        return jsonify({'success': False, 'error': 'Target must be between 0 and 100'}), 400
    
    if trend_lookback_minutes < 1 or trend_lookback_minutes > 60:
        return jsonify({'success': False, 'error': 'Trend lookback must be between 1 and 60 minutes'}), 400
    
    # Update settings
    db = Database()
    success = db.create_or_update_tre_settings(
        user_id=user_id,
        stop_loss_percent=stop_loss_percent,
        target_percent=target_percent,
        trend_lookback_minutes=trend_lookback_minutes,
        is_active=is_active
    )
    
    if success:
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to update settings'}), 500


@tre_bp.route('/api/process-alert', methods=['POST'])
def process_alert():
    """
    API endpoint to receive triggered alerts from alert system.
    This is called by the alert monitor when an alert is triggered.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400
    
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'user_id is required'}), 400
    
    # Process alert through TRE
    tre_service = TREService(user_id)
    success, trade_signal_id, error = tre_service.process_alert(data)
    
    if success:
        return jsonify({
            'success': True,
            'trade_signal_id': trade_signal_id,
            'message': 'Trade signal generated successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to process alert'
        }), 400


@tre_bp.route('/api/signals', methods=['GET'])
@login_required
def get_signals():
    """API endpoint to get trade signals."""
    user_id = session.get('user_id')
    status = request.args.get('status')  # Optional filter
    
    tre_service = TREService(user_id)
    signals = tre_service.get_user_trade_signals(user_id, status=status)
    
    return jsonify({
        'success': True,
        'signals': signals,
        'count': len(signals)
    })


@tre_bp.route('/api/signals/<int:signal_id>/status', methods=['PUT'])
@login_required
def update_signal_status(signal_id):
    """API endpoint to update trade signal status."""
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data or 'status' not in data:
        return jsonify({'success': False, 'error': 'status is required'}), 400
    
    status = data['status']
    valid_statuses = ['pending', 'sent', 'executed', 'closed', 'cancelled']
    if status not in valid_statuses:
        return jsonify({'success': False, 'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    tre_service = TREService(user_id)
    success = tre_service.update_trade_signal_status(signal_id, status)
    
    if success:
        return jsonify({'success': True, 'message': 'Signal status updated'})
    else:
        return jsonify({'success': False, 'error': 'Failed to update signal status'}), 400

