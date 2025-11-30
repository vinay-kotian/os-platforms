"""
Level routes for managing trading levels
"""
from flask import Blueprint, request, jsonify
from .level_service import LevelService
from app.auth.middleware import login_required, get_current_user_id

levels_bp = Blueprint('levels', __name__, url_prefix='/levels')
level_service = LevelService()


@levels_bp.route('/save', methods=['POST'])
@login_required
def save_level():
    """API endpoint to save or update a level"""
    try:
        user_id = get_current_user_id()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        index_type = data.get('index_type')
        level_value = data.get('level_value')
        level_uuid = data.get('uuid')  # Optional: for updating
        stock_symbol = data.get('stock_symbol')
        stock_exchange = data.get('stock_exchange')
        stop_loss = data.get('stop_loss')
        target_percentage = data.get('target_percentage')
        
        # Default expiry_type: 'persistent' for stocks, 'today' for indices
        default_expiry = 'persistent' if stock_symbol or (index_type and ':' in index_type) else 'today'
        expiry_type = data.get('expiry_type', default_expiry)  # 'today', 'persistent', or 'expiry_date'
        expiry_date = data.get('expiry_date')  # Required if expiry_type is 'expiry_date'
        
        # Validate required fields
        if not index_type or level_value is None:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: index_type, level_value'
            }), 400
        
        # Convert stop_loss and target_percentage to float if provided
        stop_loss_float = float(stop_loss) if stop_loss not in [None, ''] else None
        target_percentage_float = float(target_percentage) if target_percentage not in [None, ''] else None
        
        # Parse stock symbol from index_type if needed
        if ':' in index_type and not stock_symbol:
            parts = index_type.split(':')
            if len(parts) == 2:
                stock_exchange = parts[0]
                stock_symbol = index_type
        
        # Save level
        success, level, error = level_service.save_level(
            user_id, index_type, level_value, level_uuid,
            stock_symbol, stock_exchange, stop_loss_float, target_percentage_float,
            expiry_type, expiry_date
        )
        
        if success and level:
            return jsonify({
                'success': True,
                'uuid': level.uuid,
                'level': level.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': error or 'Failed to save level'
            }), 400
            
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid value: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error saving level: {str(e)}'
        }), 500


@levels_bp.route('/get', methods=['GET'])
@login_required
def get_levels():
    """API endpoint to get all levels"""
    try:
        user_id = get_current_user_id()
        index_type = request.args.get('index_type')  # Optional filter
        today_only = request.args.get('today_only', 'false').lower() == 'true'
        stock_symbol = request.args.get('stock_symbol')  # Optional: get levels for specific stock
        active_only = request.args.get('active_only', 'true').lower() == 'true'  # Filter expired levels
        
        # Get levels (grouped by instrument)
        levels_dict = level_service.get_levels(
            user_id, index_type, today_only, stock_symbol, grouped=True, active_only=active_only
        )
        
        # If stock_symbol was provided, return as array for that stock
        if stock_symbol:
            # Try multiple keys - stock_symbol might be stored as index_type or as stock_symbol
            stock_levels = levels_dict.get(stock_symbol, [])
            # Also check if it's in any other key (for backward compatibility)
            if not stock_levels:
                for key, levels in levels_dict.items():
                    if stock_symbol in key or key == stock_symbol:
                        stock_levels = levels
                        break
            print(f"DEBUG: Stock symbol '{stock_symbol}' - Found {len(stock_levels)} levels in levels_dict keys: {list(levels_dict.keys())}")
            return jsonify({
                'success': True,
                'levels': [level.to_dict() for level in stock_levels]
            }), 200
        
        # Convert to dict format with lists
        result = {}
        for key, levels in levels_dict.items():
            result[key] = [level.to_dict() for level in levels]
        
        # Ensure backward compatibility with old format
        if 'BANK_NIFTY' not in result:
            result['BANK_NIFTY'] = []
        if 'NIFTY_50' not in result:
            result['NIFTY_50'] = []
        
        return jsonify({
            'success': True,
            'levels': result
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting levels: {str(e)}'
        }), 500


@levels_bp.route('/get/<uuid>', methods=['GET'])
@login_required
def get_level(uuid: str):
    """API endpoint to get a specific level by UUID"""
    try:
        user_id = get_current_user_id()
        level = level_service.get_level(uuid, user_id)
        
        if level:
            return jsonify({
                'success': True,
                'level': level.to_dict()
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Level not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting level: {str(e)}'
        }), 500


@levels_bp.route('/delete/<uuid>', methods=['DELETE'])
@login_required
def delete_level(uuid: str):
    """API endpoint to delete a level"""
    try:
        user_id = get_current_user_id()
        success, error = level_service.delete_level(uuid, user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Level deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': error or 'Level not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error deleting level: {str(e)}'
        }), 500


@levels_bp.route('/clear', methods=['POST', 'DELETE'])
@login_required
def clear_levels():
    """API endpoint to clear levels"""
    try:
        user_id = get_current_user_id()
        data = request.get_json() if request.is_json else {}
        
        index_type = data.get('index_type') or request.args.get('index_type')
        today_only = data.get('today_only', False) or request.args.get('today_only', 'false').lower() == 'true'
        stock_symbol = data.get('stock_symbol') or request.args.get('stock_symbol')
        
        deleted_count, error = level_service.clear_levels(
            user_id, index_type, today_only, stock_symbol
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} level(s)',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error clearing levels: {str(e)}'
        }), 500


@levels_bp.route('/validate', methods=['POST'])
@login_required
def validate_level():
    """API endpoint to validate level parameters"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        level_value = data.get('level_value')
        current_price = data.get('current_price')
        stop_loss = data.get('stop_loss')
        target_percentage = data.get('target_percentage')
        
        if level_value is None:
            return jsonify({
                'success': False,
                'error': 'level_value is required'
            }), 400
        
        # Convert to float
        try:
            level_value = float(level_value)
            current_price = float(current_price) if current_price is not None else None
            stop_loss = float(stop_loss) if stop_loss not in [None, ''] else None
            target_percentage = float(target_percentage) if target_percentage not in [None, ''] else None
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid numeric values'
            }), 400
        
        is_valid, error = level_service.validate_level(
            level_value, current_price, stop_loss, target_percentage
        )
        
        if is_valid:
            # Calculate prices
            stop_loss_price = level_value * (1 - stop_loss / 100) if stop_loss else None
            target_price = level_value * (1 + target_percentage / 100) if target_percentage else None
            
            return jsonify({
                'success': True,
                'valid': True,
                'stop_loss_price': stop_loss_price,
                'target_price': target_price
            }), 200
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'error': error
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error validating level: {str(e)}'
        }), 500


@levels_bp.route('/api/expired', methods=['GET'])
@login_required
def get_expired_levels():
    """API endpoint to get expired levels"""
    try:
        user_id = get_current_user_id()
        index_type = request.args.get('index_type')
        stock_symbol = request.args.get('stock_symbol')
        
        # Get all levels (including expired)
        levels_dict = level_service.get_levels(
            user_id, index_type, today_only=False, stock_symbol=stock_symbol,
            grouped=True, active_only=False
        )
        
        # Filter to only expired levels
        expired_levels = {}
        for key, levels in levels_dict.items():
            expired = [level for level in levels if not level.is_active()]
            if expired:
                expired_levels[key] = [level.to_dict() for level in expired]
        
        return jsonify({
            'success': True,
            'expired_levels': expired_levels,
            'count': sum(len(levels) for levels in expired_levels.values())
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error getting expired levels: {str(e)}'
        }), 500


@levels_bp.route('/api/cleanup-expired', methods=['POST'])
@login_required
def cleanup_expired_levels():
    """API endpoint to delete expired levels"""
    try:
        user_id = get_current_user_id()
        index_type = request.args.get('index_type')
        stock_symbol = request.args.get('stock_symbol')
        
        # Get all levels (including expired)
        levels_dict = level_service.get_levels(
            user_id, index_type, today_only=False, stock_symbol=stock_symbol,
            grouped=True, active_only=False
        )
        
        # Delete expired levels
        deleted_count = 0
        for levels in levels_dict.values():
            for level in levels:
                if not level.is_active():
                    success, _ = level_service.delete_level(level.uuid, user_id)
                    if success:
                        deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} expired level(s)',
            'deleted_count': deleted_count
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error cleaning up expired levels: {str(e)}'
        }), 500

