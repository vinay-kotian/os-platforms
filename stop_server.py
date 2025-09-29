#!/usr/bin/env python3
"""
Script to stop any running Flask instances on port 5002
"""
import socket
import sys

def stop_server():
    port = 5002
    
    try:
        # Check if port is in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is in use. Server is running.")
            print("🛑 To stop the server, press Ctrl+C in the terminal where it's running.")
            print("   Or kill the process manually:")
            print(f"   lsof -ti:{port} | xargs kill -9")
        else:
            print(f"ℹ️  Port {port} is not in use. No server running.")
            
    except Exception as e:
        print(f"Error checking port {port}: {e}")

if __name__ == '__main__':
    stop_server()
