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
        rate_limit_error = None
        
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
                try:
                    price_data = price_service.get_price(exchange, symbol)
                    if price_data:
                        result[f"{exchange}:{symbol}"] = price_data.to_dict()
                except Exception as e:
                    error_msg = str(e)
                    # Check for rate limit errors
                    if "Too many requests" in error_msg or "rate limit" in error_msg.lower():
                        rate_limit_error = error_msg
                        # Stop processing more stocks to avoid further rate limit hits
                        break
                    # For other errors, just skip this stock
                    print(f"Error fetching price for {exchange}:{symbol}: {error_msg}")
            
            # Add small delay between requests to avoid rate limits (50ms)
            import time
            time.sleep(0.05)
        
        # If we hit a rate limit, return error
        if rate_limit_error:
            return jsonify({
                'success': False,
                'error': rate_limit_error
            }), 429  # HTTP 429 Too Many Requests
        
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


@prices_bp.route('/api/search', methods=['GET'])
@login_required
def api_search_instruments():
    """API endpoint to search for instruments by symbol or name"""
    try:
        query = request.args.get('q', '').strip()
        exchange = request.args.get('exchange', 'NSE')
        limit = int(request.args.get('limit', 20))
        
        if not query or len(query) < 2:
            return jsonify({
                'success': True,
                'instruments': []
            }), 200
        
        # Use ExchangeClient to search
        exchange_client = ExchangeClient()
        results = exchange_client.search_instruments(query, exchange, limit)
        
        return jsonify({
            'success': True,
            'instruments': results
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error searching instruments: {str(e)}'
        }), 500


# Legacy endpoint for backward compatibility
@prices_bp.route('/api/fetch-websocket', methods=['GET'])
@login_required
def api_fetch_prices_websocket():
    """API endpoint to fetch prices using WebSocket (legacy endpoint)"""
    return api_fetch_prices()


@prices_bp.route('/api/subscribe', methods=['POST'])
@login_required
def api_subscribe_stock():
    """API endpoint to subscribe a custom stock to WebSocket for real-time updates"""
    try:
        data = request.get_json()
        exchange = data.get('exchange', 'NSE')
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Missing required parameter: symbol'
            }), 400
        
        # Import the subscription function
        from services import subscribe_custom_stock_to_websocket
        
        success = subscribe_custom_stock_to_websocket(exchange, symbol)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Subscribed {exchange}:{symbol} to WebSocket'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to subscribe {exchange}:{symbol} to WebSocket. WebSocket may not be running.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error subscribing stock: {str(e)}'
        }), 500

