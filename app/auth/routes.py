"""
Authentication routes for login and user management.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from app.database.models import Database
from app.auth.auth_service import AuthService
from app.auth.middleware import login_required, admin_required


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    try:
        db = Database()
        auth_service = AuthService(db)
        
        # If already logged in, redirect to home
        if auth_service.is_authenticated():
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                flash('Username and password are required', 'error')
                return render_template('auth/login.html')
            
            success, user, error = auth_service.login(username, password)
            
            if success:
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('index'))
            else:
                flash(error or 'Login failed', 'error')
        
        return render_template('auth/login.html')
    except Exception as e:
        # Log error without printing to stderr (which can interfere with WSGI)
        import logging
        logging.error(f"Error in login route: {e}", exc_info=True)
        # Return a proper response even on error
        try:
            flash('An error occurred. Please try again.', 'error')
            return render_template('auth/login.html')
        except:
            from flask import Response
            return Response('Internal Server Error', status=500, mimetype='text/plain')


@auth_bp.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    """User logout."""
    db = Database()
    auth_service = AuthService(db)
    auth_service.logout()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/admin/users', methods=['GET'])
@admin_required
def list_users():
    """List all users (admin only)."""
    db = Database()
    users = db.get_all_users()
    
    # Remove password hashes from response
    users_data = [user.to_dict() for user in users]
    
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({'users': users_data})
    
    return render_template('auth/users.html', users=users_data)


@auth_bp.route('/admin/users/create', methods=['POST'])
@admin_required
def create_user():
    """Create a new user (admin only)."""
    db = Database()
    
    if request.is_json:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        is_admin = data.get('is_admin', False)
    else:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        is_admin = request.form.get('is_admin') == 'on' or request.form.get('is_admin') == 'true'
    
    if not username or not password:
        error_msg = 'Username and password are required'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('auth.list_users'))
    
    if len(password) < 6:
        error_msg = 'Password must be at least 6 characters long'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('auth.list_users'))
    
    user = db.create_user(username, password, is_admin)
    
    if user:
        success_msg = f'User {username} created successfully'
        if request.is_json:
            return jsonify({
                'success': True,
                'message': success_msg,
                'user': user.to_dict()
            }), 201
        flash(success_msg, 'success')
    else:
        error_msg = f'Username {username} already exists'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
    
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)."""
    db = Database()
    auth_service = AuthService(db)
    
    # Prevent self-deletion
    current_user = auth_service.get_current_user()
    if current_user and current_user.user_id == user_id:
        error_msg = 'You cannot delete your own account'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('auth.list_users'))
    
    deleted = db.delete_user(user_id)
    
    if deleted:
        success_msg = 'User deleted successfully'
        if request.is_json:
            return jsonify({'success': True, 'message': success_msg})
        flash(success_msg, 'success')
    else:
        error_msg = 'User not found'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 404
        flash(error_msg, 'error')
    
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user information."""
    db = Database()
    auth_service = AuthService(db)
    user = auth_service.get_current_user()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'user': user.to_dict()})

