#!/usr/bin/env python3
"""
Script to start the Flask server with proper process management
"""
import os
import sys
import subprocess
import time

def start_server():
    port = 5002
    
    print("🔍 Checking for existing instances...")
    
    # Check if port is already in use
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"❌ Port {port} is already in use!")
            print("🛑 Please stop the existing server first:")
            print("   - Press Ctrl+C in the terminal where it's running")
            print("   - Or run: python3 stop_server.py")
            return False
    except Exception as e:
        print(f"Warning: Could not check port {port}: {e}")
    
    print(f"🚀 Starting Flask server on port {port}...")
    print("📊 Features enabled:")
    print("   - Three levels database storage")
    print("   - Alert synchronization with Zerodha")
    print("   - Price crossing detection")
    print("   - Single process mode (no auto-reloader)")
    print()
    print("🌐 Server will be available at: http://localhost:5002")
    print("🛑 To stop: Press Ctrl+C")
    print("-" * 50)
    
    # Start the server
    try:
        subprocess.run([sys.executable, 'app.py'], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False
    
    return True

if __name__ == '__main__':
    start_server()
