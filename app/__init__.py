"""
App package initialization.
"""
import os
from flask import Flask, render_template, redirect, url_for, session, Response
from flask_socketio import SocketIO
from app.auth.routes import auth_bp
from app.prices.routes import prices_bp
from app.alerts.routes import alerts_bp
from app.history.routes import history_bp
from app.tre.routes import tre_bp
from app.oop.routes import oop_bp
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
        logger=False,  # Disable logging to reduce console output
        engineio_logger=False  # Disable engineio logging to reduce console output
    )
    app.socketio = socketio
    
    # Initialize database
    db = Database()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(tre_bp)
    app.register_blueprint(oop_bp)
    
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
    
    # Initialize and start OOP order monitor
    from app.oop.oop_service import get_oop_service
    oop_service = get_oop_service()
    oop_service.start_monitoring()  # Start monitoring orders
    app.oop_service = oop_service  # Make it accessible via app context
    
    # Root route - redirect to prices if logged in, otherwise to login
    @app.route('/')
    def index():
        """Home page - redirects to prices if logged in."""
        try:
            if 'user_id' in session:
                return redirect(url_for('prices.index'))
            return redirect(url_for('auth.login'))
        except Exception as e:
            # Log error without printing to stderr (which can interfere with WSGI)
            import logging
            logging.error(f"Error in root route: {e}", exc_info=True)
            # Ensure we always return a proper response
            try:
                return redirect(url_for('auth.login'))
            except:
                # Last resort - return a simple response
                return Response('Internal Server Error', status=500, mimetype='text/plain')
    
    # Global error handler to catch unexpected exceptions (WSGI-safe)
    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """Handle all exceptions and return a simple, safe response."""
        import logging
        logging.error(f"Unexpected error: {e}", exc_info=True)
        # Always return a simple response to avoid WSGI write-before-start issues
        return Response('Internal Server Error', status=500, mimetype='text/plain')
    
    # Explicit 500 handler (kept minimal)
    @app.errorhandler(500)
    def handle_500_error(e):
        import logging
        logging.error(f"Internal server error: {e}", exc_info=True)
        return Response('Internal Server Error', status=500, mimetype='text/plain')
    
    return app

