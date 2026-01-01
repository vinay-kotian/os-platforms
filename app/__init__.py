"""
App package initialization.
"""
import os
from flask import Flask, render_template, redirect, url_for, session
from flask_socketio import SocketIO
from app.auth.routes import auth_bp
from app.prices.routes import prices_bp
from app.alerts.routes import alerts_bp
from app.history.routes import history_bp
from app.database.models import Database
from app.auth.auth_service import AuthService


def create_app():
    """Create and configure Flask application."""
    # Get the root directory (parent of app package)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(root_dir, 'templates')
    static_dir = os.path.join(root_dir, 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    app.secret_key = 'your-secret-key-change-this-in-production'  # Change this in production!
    
    # Initialize SocketIO with session management
    # SocketIO will use Flask's session for authentication
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*", 
        async_mode='threading',
        manage_session=True,  # SocketIO manages session - allows access during handshake
        cookie=None,  # Use Flask's session cookie
        allow_upgrades=True,  # Allow WebSocket upgrades
        ping_timeout=60,
        ping_interval=25,
        logger=True,  # Enable logging for debugging
        engineio_logger=True  # Enable engineio logging
    )
    app.socketio = socketio
    
    # Initialize database
    db = Database()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(history_bp)
    
    # Register SocketIO handlers
    from app.prices.routes import register_socketio_handlers
    register_socketio_handlers(socketio, app)
    
    # Initialize and start price publisher for internal pub/sub
    from app.prices.price_publisher import PricePublisher
    price_publisher = PricePublisher()
    price_publisher.start()
    app.price_publisher = price_publisher  # Make it accessible via app context
    
    # Initialize and start alert monitor
    from app.alerts.alert_monitor import AlertMonitor
    alert_monitor = AlertMonitor()
    alert_monitor.start()  # Start monitoring price updates
    app.alert_monitor = alert_monitor  # Make it accessible via app context
    
    # Root route - redirect to prices if logged in, otherwise to login
    @app.route('/')
    def index():
        """Home page - redirects to prices if logged in."""
        if 'user_id' in session:
            return redirect(url_for('prices.index'))
        return redirect(url_for('auth.login'))
    
    return app

