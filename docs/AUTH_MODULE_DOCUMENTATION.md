# Authentication Module Documentation

## Overview

A complete user authentication system has been created for the OS Platforms Trading System. This module allows multiple users to register, login, and manage their own trading data.

## What Was Created

### 1. **Module Structure** (`app/auth/`)

```
app/auth/
├── __init__.py              # Module exports
├── models.py                # User domain models (User, UserSession)
├── user_repository.py       # Database operations for users
├── auth_service.py          # Business logic (registration, login, password management)
├── routes.py                # Flask routes (web and API)
├── middleware.py            # @login_required decorator
├── helpers.py               # Helper functions (get_current_user_id, etc.)
└── README.md                # Module documentation
```

### 2. **Templates** (`templates/auth/`)

```
templates/auth/
├── login.html               # User login page
└── register.html            # User registration page
```

### 3. **Database Schema**

New `users` table created with:
- `id` (Primary Key)
- `username` (Unique)
- `email` (Unique)
- `password_hash` (SHA-256 with salt)
- `is_active` (Boolean)
- `created_at`, `updated_at`, `last_login` (Timestamps)

## Features

### ✅ User Registration
- Username (min 3 characters)
- Email (validated)
- Password (min 6 characters)
- Password confirmation
- Unique username/email validation

### ✅ User Login
- Username/password authentication
- Session management
- "Remember me" option
- Last login tracking

### ✅ Password Security
- SHA-256 hashing with random salt
- Secure password storage
- Password change functionality

### ✅ Session Management
- Flask session-based
- User ID stored in session
- Automatic session cleanup on logout

### ✅ Route Protection
- `@login_required` decorator
- Automatic redirect to login if not authenticated
- API endpoints return 401 if not authenticated

### ✅ API Endpoints
- RESTful API for programmatic access
- JSON request/response format
- Consistent error handling

## Routes

### Web Routes
- `GET/POST /auth/register` - Registration page
- `GET/POST /auth/login` - Login page  
- `GET/POST /auth/logout` - Logout

### API Routes
- `POST /auth/api/register` - Register user (JSON)
- `POST /auth/api/login` - Login user (JSON)
- `POST /auth/api/logout` - Logout user (JSON)
- `GET /auth/api/me` - Get current user info
- `POST /auth/api/change-password` - Change password

## Integration with Existing System

### Changes Made to `app.py`

1. **Registered Auth Blueprint**
   ```python
   from app.auth.routes import auth_bp
   app.register_blueprint(auth_bp)
   ```

2. **Updated Index Route**
   - Now redirects to `/auth/login` if user not logged in
   - Checks for user session before Zerodha connection

3. **Renamed Zerodha Routes**
   - `/login` → `/zerodha/login` (Zerodha API credentials)
   - `/callback` → `/zerodha/callback`
   - `/logout` → `/zerodha/logout` (disconnects Zerodha only)

4. **Added Route Protection**
   - `/prices` now requires user login
   - `/zerodha/login` requires user login

## Usage Examples

### Protecting a Route

```python
from app.auth.middleware import login_required

@app.route('/my-route')
@login_required
def my_route():
    user_id = get_current_user_id()
    # Your code here
```

### Getting Current User

```python
from app.auth.helpers import get_current_user_id, get_current_username

# In a route or service
user_id = get_current_user_id()  # Returns user ID or 'default_user' as fallback
username = get_current_username()  # Returns username or None
```

### Using Auth Service Directly

```python
from app.auth import AuthService

auth_service = AuthService()

# Register
success, user, error = auth_service.register_user(
    username='john_doe',
    email='john@example.com',
    password='secure123'
)

# Login
success, user, error = auth_service.login_user(
    username='john_doe',
    password='secure123'
)
```

## API Usage Examples

### Register User
```bash
curl -X POST http://localhost:5001/auth/api/register \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "trader1",
    "email": "trader1@example.com",
    "password": "password123"
  }'
```

### Login
```bash
curl -X POST http://localhost:5001/auth/api/login \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "trader1",
    "password": "password123"
  }'
```

### Get Current User
```bash
curl http://localhost:5001/auth/api/me \
  -H 'Cookie: session=...'
```

### Change Password
```bash
curl -X POST http://localhost:5001/auth/api/change-password \
  -H 'Content-Type: application/json' \
  -H 'Cookie: session=...' \
  -d '{
    "old_password": "password123",
    "new_password": "newpassword456"
  }'
```

## User Flow

### New User Flow
1. User visits `/` → Redirected to `/auth/login`
2. User clicks "Create account" → Goes to `/auth/register`
3. User registers → Redirected to `/auth/login`
4. User logs in → Redirected to `/prices`
5. User connects Zerodha → Can start trading

### Existing User Flow
1. User visits `/` → Redirected to `/auth/login`
2. User logs in → Redirected to `/prices`
3. If Zerodha not connected → Prompted to connect
4. User can trade → All data scoped to their user_id

## Database Integration

### Current State
- All existing functions use `user_id='default_user'` as default
- This ensures backward compatibility

### Migration Path
Functions should be updated to use `get_current_user_id()`:

```python
# Before
def get_levels(user_id='default_user', ...):
    ...

# After
from app.auth.helpers import get_current_user_id

def get_levels(user_id=None, ...):
    if user_id is None:
        user_id = get_current_user_id()
    ...
```

## Security Considerations

1. **Password Hashing**: SHA-256 with random salt per user
2. **Session Security**: Flask sessions with secret key
3. **Input Validation**: All inputs validated before processing
4. **SQL Injection**: Parameterized queries used throughout
5. **XSS Protection**: Templates escape user input

## Testing

### Manual Testing
1. Visit `http://localhost:5001/auth/register`
2. Create a new account
3. Login at `http://localhost:5001/auth/login`
4. Verify session persists
5. Test logout

### API Testing
Use the curl examples above or Postman/Insomnia

## Next Steps

1. **Update Services**: Modify functions in `services.py` to use `get_current_user_id()`
2. **User Dashboard**: Create user profile page
3. **Password Reset**: Add forgot password functionality
4. **Email Verification**: Add email verification on registration
5. **User Management**: Admin panel for user management (optional)

## Files Created

1. `app/auth/__init__.py`
2. `app/auth/models.py`
3. `app/auth/user_repository.py`
4. `app/auth/auth_service.py`
5. `app/auth/routes.py`
6. `app/auth/middleware.py`
7. `app/auth/helpers.py`
8. `app/auth/README.md`
9. `templates/auth/login.html`
10. `templates/auth/register.html`
11. `docs/AUTH_MODULE_DOCUMENTATION.md` (this file)

## Integration Status

✅ **Completed:**
- User registration and login
- Session management
- Route protection
- API endpoints
- Database schema
- Templates

🔄 **In Progress:**
- Updating existing services to use user_id from session

⏳ **Future:**
- Password reset
- Email verification
- User profile management
- Admin features

---

**Last Updated**: November 28, 2025
**Module Version**: 1.0

