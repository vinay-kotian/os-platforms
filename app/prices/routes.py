"""
Price routes for fetching and displaying stock prices
"""
from flask import Blueprint, render_template, jsonify, session, request
from .price_service import PriceService
from .exchange_client import ExchangeClient
from app.auth.middleware import login_required, get_current_user_id

prices_bp = Blueprint('prices', __name__, url_prefix='/prices')
price_service = PriceService()


@prices_bp.route('', methods=['GET'])
@login_required
def prices_page():
    """Prices page - displays NIFTY 50 and NIFTY BANK prices"""
    try:
        # Get prices
        prices_dict = price_service.get_nifty_prices(use_websocket=True)
        
        # Convert to dict format for template
        prices_data = {}
        if 'nifty' in prices_dict:
            prices_data['nifty'] = prices_dict['nifty'].to_dict()
        if 'bank_nifty' in prices_dict:
            prices_data['bank_nifty'] = prices_dict['bank_nifty'].to_dict()
        
        # Get Zerodha tokens from session if available
        access_token_display = session.get('access_token')
        request_token = session.get('request_token')
        
        return render_template(
            'prices.html',
            prices=prices_data,
            access_token=access_token_display,
            request_token=request_token
        )
    except Exception as e:
        return render_template('prices.html', prices=None, error=str(e))


@prices_bp.route('/api/fetch', methods=['GET'])
@login_required
def api_fetch_prices():
    """API endpoint to fetch current stock prices"""
    try:
        use_websocket = request.args.get('websocket', 'true').lower() == 'true'
        
        prices_dict = price_service.get_nifty_prices(use_websocket=use_websocket)
        
        # Convert to dict format
        result = {}
        if 'nifty' in prices_dict:
            result['nifty'] = prices_dict['nifty'].to_dict()
        if 'bank_nifty' in prices_dict:
            result['bank_nifty'] = prices_dict['bank_nifty'].to_dict()
        
        return jsonify({
            'success': True,
            'prices': result
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching prices: {str(e)}'
        }), 500


@prices_bp.route('/api/quote', methods=['GET'])
@login_required
def api_get_quote():
    """API endpoint to get quote for a specific instrument"""
    try:
        exchange = request.args.get('exchange', 'NSE')
        tradingsymbol = request.args.get('symbol')
        
        if not tradingsymbol:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: symbol'
            }), 400
        
        price_data = price_service.get_price(exchange, tradingsymbol)
        
        if not price_data:
            return jsonify({
                'success': False,
                'error': f'Could not fetch price for {exchange}:{tradingsymbol}'
            }), 404
        
        return jsonify({
            'success': True,
            'price': price_data.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching quote: {str(e)}'
        }), 500


@prices_bp.route('/api/quotes', methods=['GET', 'POST'])
@login_required
def api_get_quotes():
    """API endpoint to get quotes for multiple instruments"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            stocks = data.get('stocks', [])
        else:
            # GET request - parse from query params
            stocks_param = request.args.get('stocks', '')
            if stocks_param:
                # Format: "NSE:RELIANCE,NSE:TCS" or JSON array
                try:
                    import json
                    stocks = json.loads(stocks_param)
                except:
                    stocks = [s.strip() for s in stocks_param.split(',') if s.strip()]
            else:
                stocks = []
        
        if not stocks:
            return jsonify({
                'success': False,
                'error': 'No stocks provided'
            }), 400
        
        # Fetch quotes for all stocks
        result = {}
        for stock in stocks:
            # Handle both "NSE:RELIANCE" and {"exchange": "NSE", "symbol": "RELIANCE"} formats
            if isinstance(stock, dict):
                exchange = stock.get('exchange', 'NSE')
                symbol = stock.get('symbol', '')
            else:
                # Parse "NSE:RELIANCE" format
                parts = stock.split(':')
                if len(parts) == 2:
                    exchange = parts[0]
                    symbol = parts[1]
                else:
                    exchange = 'NSE'
                    symbol = stock
            
            if symbol:
                price_data = price_service.get_price(exchange, symbol)
                if price_data:
                    result[f"{exchange}:{symbol}"] = price_data.to_dict()
        
        return jsonify({
            'success': True,
            'prices': result
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching quotes: {str(e)}'
        }), 500


@prices_bp.route('/api/status', methods=['GET'])
@login_required
def api_get_status():
    """API endpoint to check price service status"""
    try:
        return jsonify({
            'success': True,
            'exchange_connected': price_service.is_exchange_connected(),
            'websocket_running': price_service.is_websocket_running()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error checking status: {str(e)}'
        }), 500


# Legacy endpoint for backward compatibility
@prices_bp.route('/api/fetch-websocket', methods=['GET'])
@login_required
def api_fetch_prices_websocket():
    """API endpoint to fetch prices using WebSocket (legacy endpoint)"""
    return api_fetch_prices()

