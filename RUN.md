# How to Run the Application

## Quick Start

Run the Flask application using one of these methods:

### Method 1: Direct execution (Recommended)
```bash
python3 app.py
```

### Method 2: Using the start script
```bash
python3 start_server.py
```

### Method 3: As a module
```bash
python3 -m app
```

## Important Notes

- **Do NOT run**: `python3 -m app.auth` or `python3 app` (without the `.py`)
- The main application file is `app.py` (the file), not the `app/` package
- The `app/` directory is a Python package containing modules (like `app/auth/`)
- The `app.py` file is the Flask application entry point

## Port

The server runs on port **5001** by default (or 5002 if using `start_server.py`)

## Access

Once running, access the application at:
- http://localhost:5001 (or http://localhost:5002)

## Troubleshooting

If you see: `'app' is a package and cannot be directly executed`
- Make sure you're running `python3 app.py` (with `.py`)
- Or use `python3 -m app` (with the `-m` flag)

