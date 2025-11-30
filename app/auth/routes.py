"""
Authentication routes for user login and registration
Includes user authentication and Zerodha API authentication
"""
import os
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from kiteconnect import KiteConnect
from .auth_service import AuthService
from .user_repository import UserRepository
from .middleware import login_required

# Import services for Zerodha session management
try:
    import services
    from services import save_session_data, SESSION_FILE
except ImportError:
    # Fallback if services not available
    SESSION_FILE = 'session_data.json'
    def save_session_data():
        pass

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
auth_service = AuthService()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html')
        
        # Register user
        success, user, error = auth_service.register_user(username, email, password)
        
        if success:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(error or 'Registration failed', 'error')
            return render_template('auth/register.html', username=username, email=email)
    
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    # If already logged in, redirect to dashboard
    if session.get('user_id'):
        try:
            return redirect(url_for('prices.prices_page'))
        except:
            return redirect('/prices')
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'
        
        # Authenticate user
        success, user, error = auth_service.login_user(username, password)
        
        if success and user:
            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            session['email'] = user.email
            
            # Set session permanence
            if remember_me:
                session.permanent = True
            
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to intended page or dashboard
            try:
                next_page = request.args.get('next') or url_for('prices.prices_page')
            except:
                next_page = request.args.get('next') or '/prices'
            return redirect(next_page)
        else:
            flash(error or 'Login failed', 'error')
            return render_template('auth/login.html', username=username)
    
    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """User logout"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}! You have been logged out.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """API endpoint for user registration"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided', 'success': False}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    success, user, error = auth_service.register_user(username, email, password)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 201
    else:
        return jsonify({
            'success': False,
            'error': error or 'Registration failed'
        }), 400


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for user login"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided', 'success': False}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    success, user, error = auth_service.login_user(username, password)
    
    if success and user:
        # Set session
        session['user_id'] = user.id
        session['username'] = user.username
        session['email'] = user.email
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': error or 'Login failed'
        }), 401


@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """API endpoint for user logout"""
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200


@auth_bp.route('/api/me', methods=['GET'])
def api_get_current_user():
    """API endpoint to get current logged-in user"""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Not authenticated'
        }), 401
    
    user = auth_service.get_user(user_id)
    
    if not user:
        session.clear()
        return jsonify({
            'success': False,
            'error': 'User not found'
        }), 404
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if isinstance(user.created_at, datetime) else user.created_at,
            'last_login': user.last_login.isoformat() if user.last_login and isinstance(user.last_login, datetime) else user.last_login
        }
    }), 200


@auth_bp.route('/api/change-password', methods=['POST'])
def api_change_password():
    """API endpoint to change password"""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Not authenticated'
        }), 401
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided', 'success': False}), 400
    
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    success, error = auth_service.change_password(user_id, old_password, new_password)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': error or 'Failed to change password'
        }), 400


# ============================================================================
# Zerodha API Authentication Routes
# ============================================================================

@auth_bp.route('/zerodha/login', methods=['GET', 'POST'])
@login_required
def zerodha_login():
    """Login page for Zerodha API credentials (after user authentication)"""
    # Import services module to access global variables
    try:
        import services
    except ImportError:
        flash('Services module not available', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is authenticated
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        
        if not api_key or not api_secret:
            flash('Please enter both API Key and API Secret', 'error')
            return render_template('auth/zerodha_login.html')
        
        try:
            # Store user credentials in services module
            services.user_api_key = api_key
            services.user_api_secret = api_secret
            
            # Initialize KiteConnect with user's API key
            services.kite = KiteConnect(api_key=api_key)
            kite = services.kite
            
            # Generate login URL
            login_url = kite.login_url()
            
            # Extract redirect token from login URL if present
            redirect_token = None
            try:
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(login_url)
                query_params = parse_qs(parsed_url.query)
                redirect_token = query_params.get('redirect_token') or query_params.get('request_token') or query_params.get('token')
                if redirect_token:
                    redirect_token = redirect_token[0] if isinstance(redirect_token, list) else redirect_token
            except:
                pass
            
            # Store in session for callback
            session['api_key'] = api_key
            session['api_secret'] = api_secret
            
            flash('Credentials saved! Please complete the login process.', 'success')
            return render_template('auth/zerodha_login.html', login_url=login_url, api_key=api_key, redirect_token=redirect_token)
            
        except Exception as e:
            flash(f'Error initializing KiteConnect: {str(e)}', 'error')
            return render_template('auth/zerodha_login.html')
    
    return render_template('auth/zerodha_login.html')


@auth_bp.route('/zerodha/callback')
@login_required
def zerodha_callback():
    """Handle Zerodha login callback"""
    try:
        import services
        from services import save_session_data
    except ImportError:
        flash('Services module not available', 'error')
        return redirect(url_for('auth.login'))
    
    request_token = request.args.get("request_token")
    if not request_token:
        flash('Error: No request token received', 'error')
        return redirect(url_for('auth.zerodha_login'))
    
    try:
        # Get stored credentials from session
        api_key = session.get('api_key')
        api_secret = session.get('api_secret')
        
        if not api_key or not api_secret:
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('auth.zerodha_login'))
        
        # Initialize KiteConnect with stored credentials
        services.kite = KiteConnect(api_key=api_key)
        kite = services.kite
        
        # Generate session to get access_token
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        
        # Save access token and request token in session
        session["access_token"] = access_token
        session["request_token"] = request_token
        kite.set_access_token(access_token)
        
        # Save to file for persistence
        save_session_data()
        
        flash('Zerodha login successful! You can now access stock data.', 'success')
        return redirect(url_for('prices.prices_page'))
        
    except Exception as e:
        flash(f'Zerodha login failed: {str(e)}', 'error')
        return redirect(url_for('auth.zerodha_login'))


@auth_bp.route('/zerodha/logout')
@login_required
def zerodha_logout():
    """Logout from Zerodha (but keep user session)"""
    try:
        import services
    except ImportError:
        pass
    else:
        services.user_api_key = None
        services.user_api_secret = None
        services.kite = None
    
    # Clear Zerodha session data (but keep user session)
    session.pop('access_token', None)
    session.pop('api_key', None)
    session.pop('api_secret', None)
    session.pop('request_token', None)
    
    # Remove session file
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    
    flash('Disconnected from Zerodha successfully', 'success')
    return redirect(url_for('prices.prices_page'))


# ============================================================================
# Session & Debug Routes
# ============================================================================

@auth_bp.route('/session/status', methods=['GET'])
def session_status():
    """Debug endpoint to check session status"""
    try:
        from services import kite, user_api_key, SESSION_FILE
    except ImportError:
        kite = None
        user_api_key = None
        SESSION_FILE = 'session_data.json'
    
    return jsonify({
        'user_session': {
            'user_id': session.get('user_id'),
            'username': session.get('username'),
            'email': session.get('email'),
        },
        'zerodha_session': {
            'api_key': session.get('api_key'),
            'access_token': '***' if session.get('access_token') else None,
            'session_keys': [k for k in session.keys() if k not in ['user_id', 'username', 'email']]
        },
        'global_data': {
            'user_api_key': user_api_key is not None,
            'kite_initialized': kite is not None
        },
        'session_file_exists': os.path.exists(SESSION_FILE)
    })


@auth_bp.route('/debug', methods=['GET'])
def debug_auth():
    """Debug endpoint to check authentication status"""
    try:
        from services import kite, user_api_key, SESSION_FILE
    except ImportError:
        kite = None
        user_api_key = None
        SESSION_FILE = 'session_data.json'
    
    debug_info = {
        'user_authenticated': bool(session.get('user_id')),
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'zerodha_connected': bool(session.get('access_token')),
        'session_access_token': bool(session.get('access_token')),
        'session_api_key': bool(session.get('api_key')),
        'global_kite_initialized': kite is not None,
        'global_api_key': user_api_key is not None,
        'session_file_exists': os.path.exists(SESSION_FILE)
    }
    
    if kite:
        try:
            profile = kite.profile()
            debug_info['kite_profile'] = profile.get('user_name', 'Unknown')
            debug_info['kite_status'] = 'working'
        except Exception as e:
            debug_info['kite_error'] = str(e)
            debug_info['kite_status'] = 'error'
    
    return jsonify(debug_info)

