"""
Main Flask application entry point for Eldorado.
Run with: python app.py
"""
from app import create_app


if __name__ == '__main__':
    app = create_app()
    app.socketio.run(app, debug=True, host='0.0.0.0', port=5001)
