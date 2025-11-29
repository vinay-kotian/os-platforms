# Authentication Routes Summary

All authentication-related routes have been moved to `app/auth/routes.py`.

## Routes in `app/auth/routes.py`

### User Authentication Routes

| Route | Methods | Description | Auth Required |
|-------|---------|-------------|---------------|
| `/auth/register` | GET, POST | User registration page | No |
| `/auth/login` | GET, POST | User login page | No |
| `/auth/logout` | GET, POST | User logout | No |
| `/auth/api/register` | POST | Register user (API) | No |
| `/auth/api/login` | POST | Login user (API) | No |
| `/auth/api/logout` | POST | Logout user (API) | No |
| `/auth/api/me` | GET | Get current user info | Yes |
| `/auth/api/change-password` | POST | Change password | Yes |

### Zerodha API Authentication Routes

| Route | Methods | Description | Auth Required |
|-------|---------|-------------|---------------|
| `/auth/zerodha/login` | GET, POST | Zerodha API credentials login | Yes (User) |
| `/auth/zerodha/callback` | GET | Zerodha OAuth callback | Yes (User) |
| `/auth/zerodha/logout` | GET | Disconnect Zerodha account | Yes (User) |

### Session & Debug Routes

| Route | Methods | Description | Auth Required |
|-------|---------|-------------|---------------|
| `/auth/session/status` | GET | Check session status (debug) | No |
| `/auth/debug` | GET | Debug authentication status | No |

## Route Details

### User Registration
- **Web**: `GET/POST /auth/register`
- **API**: `POST /auth/api/register`
- **Body**: `{ "username": "...", "email": "...", "password": "..." }`

### User Login
- **Web**: `GET/POST /auth/login`
- **API**: `POST /auth/api/login`
- **Body**: `{ "username": "...", "password": "..." }`

### User Logout
- **Web**: `GET/POST /auth/logout`
- **API**: `POST /auth/api/logout`

### Get Current User
- **API**: `GET /auth/api/me`
- **Returns**: User information (id, username, email, etc.)

### Change Password
- **API**: `POST /auth/api/change-password`
- **Body**: `{ "old_password": "...", "new_password": "..." }`

### Zerodha Login
- **Route**: `GET/POST /auth/zerodha/login`
- **Description**: Connect Zerodha trading account
- **Requires**: User must be logged in first
- **Form Fields**: `api_key`, `api_secret`

### Zerodha Callback
- **Route**: `GET /auth/zerodha/callback`
- **Description**: OAuth callback from Zerodha
- **Query Params**: `request_token`

### Zerodha Logout
- **Route**: `GET /auth/zerodha/logout`
- **Description**: Disconnect Zerodha (keeps user session)

### Session Status
- **Route**: `GET /auth/session/status`
- **Description**: Debug endpoint to check session state
- **Returns**: User session, Zerodha session, global state

### Debug Auth
- **Route**: `GET /auth/debug`
- **Description**: Comprehensive auth debug information
- **Returns**: Authentication status, Zerodha connection status

## Migration Notes

### Routes Removed from `app.py`
- ✅ `/login` → Moved to `/auth/zerodha/login`
- ✅ `/callback` → Moved to `/auth/zerodha/callback`
- ✅ `/logout` → Moved to `/auth/zerodha/logout`
- ✅ `/session/status` → Moved to `/auth/session/status`
- ✅ `/debug/auth` → Moved to `/auth/debug`

### Updated References
All references to these routes in `app.py` have been updated:
- `url_for('zerodha_login')` → `url_for('auth.zerodha_login')`
- `url_for('zerodha_callback')` → `url_for('auth.zerodha_callback')`
- `url_for('zerodha_logout')` → `url_for('auth.zerodha_logout')`

## Blueprint Registration

The auth blueprint is registered in `app.py`:
```python
from app.auth.routes import auth_bp
app.register_blueprint(auth_bp)
```

This makes all routes available under the `/auth` prefix.

## Templates

All auth-related templates are in `templates/auth/`:
- `templates/auth/login.html` - User login
- `templates/auth/register.html` - User registration
- `templates/auth/zerodha_login.html` - Zerodha connection

## Testing Routes

### Test User Registration
```bash
curl -X POST http://localhost:5001/auth/api/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"testuser","email":"test@example.com","password":"test123"}'
```

### Test User Login
```bash
curl -X POST http://localhost:5001/auth/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"testuser","password":"test123"}' \
  -c cookies.txt
```

### Test Get Current User
```bash
curl http://localhost:5001/auth/api/me \
  -b cookies.txt
```

### Test Session Status
```bash
curl http://localhost:5001/auth/session/status
```

### Test Debug Auth
```bash
curl http://localhost:5001/auth/debug
```

---

**Last Updated**: November 28, 2025
**All routes are now centralized in `app/auth/routes.py`**

