# Authentication Module

## Overview

The authentication module provides user registration, login, and session management for the OS Platforms Trading System.

## Features

- ✅ User registration with username, email, and password
- ✅ Secure password hashing (SHA-256 with salt)
- ✅ User login with session management
- ✅ Password change functionality
- ✅ Session-based authentication
- ✅ Protected routes with `@login_required` decorator
- ✅ API endpoints for programmatic access
- ✅ Integration with existing Zerodha authentication

## Module Structure

```
app/auth/
├── __init__.py           # Module exports
├── models.py             # User domain models
├── user_repository.py    # Database operations
├── auth_service.py       # Business logic
├── routes.py             # Flask routes
├── middleware.py         # Authentication decorators
├── helpers.py            # Helper functions
└── README.md             # This file
```

## Usage

### Protecting Routes

```python
from app.auth.middleware import login_required

@app.route('/protected')
@login_required
def protected_route():
    user_id = get_current_user_id()
    # Your code here
```

### Getting Current User

```python
from app.auth.helpers import get_current_user_id, get_current_username

user_id = get_current_user_id()  # Returns user ID or 'default_user'
username = get_current_username()  # Returns username or None
```

### Using Auth Service

```python
from app.auth import AuthService

auth_service = AuthService()

# Register user
success, user, error = auth_service.register_user(
    username='john_doe',
    email='john@example.com',
    password='secure_password'
)

# Login user
success, user, error = auth_service.login_user(
    username='john_doe',
    password='secure_password'
)
```

## API Endpoints

### Web Routes
- `GET/POST /auth/register` - User registration page
- `GET/POST /auth/login` - User login page
- `GET/POST /auth/logout` - User logout

### API Routes
- `POST /auth/api/register` - Register new user (JSON)
- `POST /auth/api/login` - Login user (JSON)
- `POST /auth/api/logout` - Logout user (JSON)
- `GET /auth/api/me` - Get current user info
- `POST /auth/api/change-password` - Change password

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login TEXT
);
```

## Security Features

1. **Password Hashing**: SHA-256 with random salt
2. **Session Management**: Flask session with optional "remember me"
3. **Input Validation**: Username (min 3 chars), password (min 6 chars)
4. **Unique Constraints**: Username and email must be unique
5. **Account Status**: Users can be deactivated

## Integration with Existing System

The auth module integrates with the existing Zerodha authentication:

1. **User Login** → User authenticates with username/password
2. **Zerodha Login** → User connects their Zerodha account (after user login)
3. **Trading** → All trading operations are scoped to the logged-in user

## Migration Notes

- Existing code using `'default_user'` will continue to work
- `get_current_user_id()` returns `'default_user'` if no user is logged in
- All database operations should use `get_current_user_id()` instead of hardcoded `'default_user'`

## Example: Updating Existing Code

**Before:**
```python
def get_levels(user_id='default_user', ...):
    # ...
```

**After:**
```python
from app.auth.helpers import get_current_user_id

def get_levels(user_id=None, ...):
    if user_id is None:
        user_id = get_current_user_id()
    # ...
```

## Testing

```python
# Test registration
curl -X POST http://localhost:5001/auth/api/register \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123"
  }'

# Test login
curl -X POST http://localhost:5001/auth/api/login \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'

# Test get current user
curl http://localhost:5001/auth/api/me
```

