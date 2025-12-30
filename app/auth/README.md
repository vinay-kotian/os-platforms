# Authentication Module

This module handles user authentication and user management for Eldorado.

## Features

- **User Login**: Secure password-based authentication
- **Admin-only User Creation**: Only users with admin privileges can create new users
- **No Sign-up**: Users cannot self-register; all accounts must be created by admins
- **Session Management**: Flask session-based authentication
- **Password Security**: Passwords are hashed using Werkzeug's password hashing

## Setup

### 1. Create the First Admin User

Before you can use the system, you need to create an admin user:

```bash
python scripts/create_admin.py
```

This will prompt you for:
- Username
- Password (minimum 6 characters)

### 2. Start the Application

```bash
python app.py
```

The application will run on `http://localhost:5001`

## Usage

### Login

1. Navigate to `/auth/login`
2. Enter your username and password
3. You'll be redirected to the home page upon successful login

### Admin Functions

Admin users can:
- View all users at `/auth/admin/users`
- Create new users (regular or admin)
- Delete users (except themselves)

### API Endpoints

#### Login
- `POST /auth/login` - Login with username and password
- `GET /auth/login` - Display login page

#### Logout
- `POST /auth/logout` - Logout current user
- `GET /auth/logout` - Logout current user

#### User Management (Admin Only)
- `GET /auth/admin/users` - List all users
- `POST /auth/admin/users/create` - Create a new user
- `POST /auth/admin/users/<user_id>/delete` - Delete a user

#### Current User
- `GET /auth/me` - Get current user information (JSON)

## Middleware

### `@login_required`
Protects routes that require authentication. Redirects to login page if not authenticated.

### `@admin_required`
Protects routes that require admin privileges. Redirects to login page if not authenticated or not admin.

## Database Schema

### Users Table
- `user_id` (INTEGER PRIMARY KEY) - Unique user identifier
- `username` (TEXT UNIQUE) - Username (must be unique)
- `password_hash` (TEXT) - Hashed password
- `is_admin` (INTEGER) - Admin flag (0 or 1)
- `created_at` (TEXT) - ISO timestamp of creation

## Security Notes

- Passwords are hashed using Werkzeug's `generate_password_hash`
- Session secret key should be changed in production (`app.py`)
- Admin users can create other admin users
- Users cannot delete their own accounts
- Minimum password length is 6 characters

