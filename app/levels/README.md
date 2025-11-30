# Levels Module

## Overview

The levels module manages trading levels, entry prices, stop loss, and target prices for various instruments (indices and stocks).

## Features

- ✅ Save and update trading levels
- ✅ Support for indices (NIFTY 50, BANK NIFTY) and custom stocks
- ✅ Stop loss and target percentage calculations
- ✅ **Expiry management**: Today-only, persistent, or expiry date
- ✅ Automatic filtering of expired levels
- ✅ Daily level management
- ✅ Level validation
- ✅ Grouped retrieval by instrument

## Module Structure

```
app/levels/
├── __init__.py              # Module exports
├── models.py                # Level domain models
├── level_repository.py      # Database operations
├── level_service.py         # Business logic
├── routes.py                # Flask routes
└── README.md                # This file
```

## Usage

### Using Level Service

```python
from app.levels import LevelService

service = LevelService()

# Save a level (today only - default)
success, level, error = service.save_level(
    user_id='user123',
    index_type='NIFTY_50',
    level_value=19500.0,
    stop_loss=2.0,  # 2% stop loss
    target_percentage=2.5,  # 2.5% target
    expiry_type='today'  # Valid only today
)

# Save a persistent level
success, level, error = service.save_level(
    user_id='user123',
    index_type='NIFTY_50',
    level_value=19500.0,
    expiry_type='persistent'  # Never expires
)

# Save a level with expiry date
success, level, error = service.save_level(
    user_id='user123',
    index_type='NIFTY_50',
    level_value=19500.0,
    expiry_type='expiry_date',
    expiry_date='2025-12-31'  # Expires on this date
)

# Get active levels only (default - excludes expired)
levels = service.get_levels(user_id='user123', index_type='NIFTY_50', grouped=True, active_only=True)

# Get all levels including expired
levels = service.get_levels(user_id='user123', index_type='NIFTY_50', grouped=True, active_only=False)

# Check if level is active
is_active = level.is_active()
expiry_info = level.get_expiry_info()

# Delete a level
success, error = service.delete_level(level_uuid, user_id)
```

## Models

### Level
- `uuid`: Unique identifier
- `user_id`: User who owns the level
- `index_type`: Instrument type ('NIFTY_50', 'BANK_NIFTY', or stock symbol)
- `level_value`: Entry price
- `stop_loss`: Stop loss percentage (e.g., 2.0 for 2%)
- `target_percentage`: Target percentage (e.g., 2.5 for 2.5%)
- `stock_symbol`: For custom stocks (e.g., 'NSE:RELIANCE')
- `stock_exchange`: Exchange name
- `expiry_type`: Expiry type ('today', 'persistent', 'expiry_date')
- `expiry_date`: Expiry date (ISO format, required if expiry_type is 'expiry_date')

### Methods
- `calculate_stop_loss_price()`: Calculate absolute stop loss price
- `calculate_target_price()`: Calculate absolute target price
- `get_instrument_key()`: Get unique key for instrument
- `is_active()`: Check if level is currently active (not expired)
- `get_expiry_info()`: Get expiry information dictionary
- `to_dict()`: Convert to dictionary

## Routes

### API Routes
- `POST /levels/save` - Save or update a level (with expiry support)
- `GET /levels/get` - Get all levels (with filters, active_only by default)
- `GET /levels/get/<uuid>` - Get specific level
- `DELETE /levels/delete/<uuid>` - Delete a level
- `POST /levels/clear` - Clear levels (with filters)
- `POST /levels/validate` - Validate level parameters
- `GET /levels/api/expired` - Get expired levels
- `POST /levels/api/cleanup-expired` - Delete expired levels

## API Examples

### Save Level

#### Today Only (Default)
```bash
curl -X POST http://localhost:5001/levels/save \
  -H 'Content-Type: application/json' \
  -d '{
    "index_type": "NIFTY_50",
    "level_value": 19500.0,
    "expiry_type": "today"
  }'
```

#### Persistent Level
```bash
curl -X POST http://localhost:5001/levels/save \
  -H 'Content-Type: application/json' \
  -d '{
    "index_type": "NIFTY_50",
    "level_value": 19500.0,
    "expiry_type": "persistent"
  }'
```

#### Level with Expiry Date
```bash
curl -X POST http://localhost:5001/levels/save \
  -H 'Content-Type: application/json' \
  -d '{
    "index_type": "NIFTY_50",
    "level_value": 19500.0,
    "expiry_type": "expiry_date",
    "expiry_date": "2025-12-31"
  }'
```

### Get Levels
```bash
curl http://localhost:5001/levels/get?index_type=NIFTY_50&today_only=true
```

### Validate Level
```bash
curl -X POST http://localhost:5001/levels/validate \
  -H 'Content-Type: application/json' \
  -d '{
    "level_value": 19500.0,
    "current_price": 19400.0,
    "stop_loss": 2.0,
    "target_percentage": 2.5
  }'
```

## Business Logic

### Stop Loss Calculation
- Stop loss is stored as percentage below entry
- Formula: `stop_loss_price = entry_price * (1 - stop_loss / 100)`

### Target Calculation
- Target is stored as percentage above entry
- Formula: `target_price = entry_price * (1 + target_percentage / 100)`

### Validation Rules
- Level value must be positive
- Stop loss must be between 0 and 100%
- Target percentage must be positive
- Target should be greater than stop loss
- Stop loss price should be below current price (if provided)

## Integration

The levels module integrates with:
- **Auth Module**: Uses `@login_required` decorator
- **Services Module**: Can use existing `save_level` and `get_levels` functions for backward compatibility

## Migration Notes

### Old Code → New Code

**Old:**
```python
from services import save_level
save_level(user_id, index_type, level_value)
```

**New:**
```python
from app.levels import LevelService
service = LevelService()
success, level, error = service.save_level(user_id, index_type, level_value)
```

### Backward Compatibility

Legacy endpoints in `app.py` are maintained and delegate to the new module routes.

---

**Last Updated**: November 29, 2025
**Module Version**: 1.0

