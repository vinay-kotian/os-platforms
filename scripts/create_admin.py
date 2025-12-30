"""
Script to create the first admin user.
Run this script to initialize the database with an admin account.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.models import Database


def create_admin():
    """Create the first admin user."""
    db = Database()
    
    print("=" * 50)
    print("Create Admin User")
    print("=" * 50)
    
    username = input("Enter username: ").strip()
    if not username:
        print("Error: Username cannot be empty")
        return
    
    password = input("Enter password (min 6 characters): ").strip()
    if len(password) < 6:
        print("Error: Password must be at least 6 characters long")
        return
    
    # Check if username already exists
    existing_user = db.get_user_by_username(username)
    if existing_user:
        print(f"Error: Username '{username}' already exists")
        return
    
    # Create admin user
    user = db.create_user(username, password, is_admin=True)
    
    if user:
        print(f"\n✓ Admin user '{username}' created successfully!")
        print(f"  User ID: {user.user_id}")
        print(f"  Is Admin: {user.is_admin}")
    else:
        print(f"\n✗ Failed to create admin user")


if __name__ == '__main__':
    create_admin()

