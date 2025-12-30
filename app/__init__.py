"""
App package initialization.
"""
import os
from flask import Flask, render_template
from app.auth.routes import auth_bp
from app.database.models import Database


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
    
    # Initialize database
    db = Database()
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    
    # Root route
    @app.route('/')
    def index():
        """Home page."""
        return render_template('index.html')
    
    return app

