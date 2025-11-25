# Repository Structure

This document describes the organized structure of the os-platforms repository.

## Directory Structure

```
os-platforms/
├── app.py                 # Main Flask application
├── start_server.py        # Server startup script
├── stop_server.py         # Server stop script
├── requirements.txt       # Python dependencies
├── README.md              # Main project documentation
├── LICENSE                # License file
├── .gitignore            # Git ignore rules
├── .vscode/              # VS Code configuration
│
├── tests/                # All test files
│   ├── test_alert_api.py
│   ├── test_alert_triggers.py
│   ├── test_database_functionality.py
│   ├── test_delete_alert.py
│   ├── test_level_retrieval.py
│   ├── test_one_time_triggers.py
│   ├── test_prices_integration.py
│   ├── test_session_debug.py
│   ├── debug_alert_api.py
│   ├── debug_response_structure.py
│   └── check_database.py
│
├── docs/                  # All documentation files
│   ├── ALERT_API_DOCUMENTATION.md
│   ├── ALERT_API_DOCUMENTATION.pdf
│   ├── ALERT_TRIGGER_DOCUMENTATION.md
│   ├── ALERT_TRIGGER_DOCUMENTATION.pdf
│   ├── ALERT_TROUBLESHOOTING.md
│   ├── ALERT_TROUBLESHOOTING.pdf
│   ├── DATABASE_API_DOCUMENTATION.md
│   ├── DATABASE_API_DOCUMENTATION.pdf
│   ├── DELETE_ALERT_DOCUMENTATION.md
│   ├── ONE_TIME_TRIGGER_DOCUMENTATION.md
│   ├── ONE_TIME_TRIGGER_DOCUMENTATION.pdf
│   ├── curl_commands.md
│   └── curl_commands.pdf
│
├── scripts/               # Shell scripts
│   ├── delete_alert_examples.sh
│   └── test_curl_commands.sh
│
├── templates/            # Flask HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── prices.html
│   ├── 404.html
│   └── 500.html
│
├── static/               # Static assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── samples/              # Sample code
│   └── test_code.py
│
└── env/                  # Python virtual environment (not in git)
```

## File Organization

### Root Directory
- **Core application files**: `app.py`, `start_server.py`, `stop_server.py`
- **Configuration**: `requirements.txt`, `.gitignore`
- **Data files**: `app.db`, `session_data.json` (gitignored)

### Tests Directory
All test files have been moved to `tests/` directory. Test files use:
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
to import from the parent directory (`app.py`).

### Documentation
All documentation files (`.md` and `.pdf`) are in the `docs/` directory, except `README.md` which remains in the root.

### Scripts
All shell scripts (`.sh`) are in the `scripts/` directory.

## Running Tests

From the root directory:
```bash
python tests/test_alert_api.py
python tests/test_level_retrieval.py
# etc.
```

## Notes

- The `env/` directory contains the Python virtual environment and is gitignored
- `app.db` and `session_data.json` are gitignored as they contain runtime data
- All test files have been updated to correctly import from the parent directory

