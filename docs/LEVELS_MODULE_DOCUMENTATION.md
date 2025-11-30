# Levels Module Documentation

## Overview

A complete modular levels management system has been created for the OS Platforms Trading System. This module handles trading levels, entry prices, stop loss, and target prices for indices and stocks.

## What Was Created

### 1. **Module Structure** (`app/levels/`)

```
app/levels/
├── __init__.py              # Module exports
├── models.py                # Level domain models
├── level_repository.py      # Database operations
├── level_service.py         # Business logic
├── routes.py                # Flask routes
└── README.md                # Module documentation
```

### 2. **Models** (`models.py`)

- **Level**: Complete level model with:
  - Entry price (level_value)
  - Stop loss percentage
  - Target percentage
  - Stock symbol support
  - Automatic price calculations
  - Type detection (NIFTY_50, BANK_NIFTY, STOCK, CUSTOM)

- **LevelType**: Enum for level types

### 3. **Repository** (`level_repository.py`)

- CRUD operations for levels
- Filtering by index_type, stock_symbol, date
- Grouped retrieval
- Bulk operations (clear levels)

### 4. **Service** (`level_service.py`)

- Business logic for level operations
- Input validation
- Price calculations
- Error handling

### 5. **Routes** (`routes.py`)

- `POST /levels/save` - Save or update level
- `GET /levels/get` - Get all levels (with filters)
- `GET /levels/get/<uuid>` - Get specific level
- `DELETE /levels/delete/<uuid>` - Delete level
- `POST /levels/clear` - Clear levels
- `POST /levels/validate` - Validate level parameters

## Features

### ✅ Level Management
- Save and update trading levels
- Support for indices (NIFTY 50, BANK NIFTY)
- Support for custom stocks (NSE:RELIANCE format)
- Multiple levels per instrument

### ✅ Stop Loss & Target
- Stop loss as percentage below entry
- Target as percentage above entry
- Automatic price calculations
- Validation rules

### ✅ Filtering & Grouping
- Filter by instrument type
- Filter by stock symbol
- Filter by date (today only)
- Grouped retrieval by instrument

### ✅ Validation
- Input validation
- Business rule validation
- Price range validation
- Stop loss/target relationship validation

## Design Improvements

### 1. **Separation of Concerns**
- Models: Data structures
- Repository: Database operations
- Service: Business logic
- Routes: HTTP handling

### 2. **Type Safety**
- Enum for level types
- Dataclasses for models
- Type hints throughout

### 3. **Calculations**
- Automatic stop loss price calculation
- Automatic target price calculation
- Built into model methods

### 4. **Validation**
- Service-level validation
- Dedicated validation endpoint
- Clear error messages

### 5. **User Scoping**
- All operations scoped to user_id
- Uses `get_current_user_id()` from auth module
- Secure by default

## API Examples

### Save Level
```bash
curl -X POST http://localhost:5001/levels/save \
  -H 'Content-Type: application/json' \
  -d '{
    "index_type": "NIFTY_50",
    "level_value": 19500.0,
    "stop_loss": 2.0,
    "target_percentage": 2.5
  }'
```

### Save Stock Level
```bash
curl -X POST http://localhost:5001/levels/save \
  -H 'Content-Type: application/json' \
  -d '{
    "index_type": "NSE:RELIANCE",
    "level_value": 2450.0,
    "stock_symbol": "NSE:RELIANCE",
    "stock_exchange": "NSE",
    "stop_loss": 1.5,
    "target_percentage": 2.0
  }'
```

### Get Levels
```bash
# Get all levels
curl http://localhost:5001/levels/get

# Get NIFTY 50 levels only
curl http://localhost:5001/levels/get?index_type=NIFTY_50

# Get today's levels only
curl http://localhost:5001/levels/get?today_only=true

# Get levels for specific stock
curl http://localhost:5001/levels/get?stock_symbol=NSE:RELIANCE
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

### Delete Level
```bash
curl -X DELETE http://localhost:5001/levels/delete/<uuid>
```

### Clear Levels
```bash
# Clear all levels
curl -X POST http://localhost:5001/levels/clear

# Clear today's levels only
curl -X POST http://localhost:5001/levels/clear \
  -H 'Content-Type: application/json' \
  -d '{"today_only": true}'

# Clear specific instrument
curl -X POST http://localhost:5001/levels/clear \
  -H 'Content-Type: application/json' \
  -d '{"index_type": "NIFTY_50"}'
```

## Integration

### With Main App

The levels module is integrated into `app.py`:
- Blueprint registered
- Legacy routes updated to use module (with fallback)
- All routes use `@login_required` decorator

### With Auth Module

- Uses `get_current_user_id()` for user scoping
- All routes protected with `@login_required`

### Backward Compatibility

- Legacy routes in `app.py` maintained
- Automatic fallback to old `services` functions if module not available
- Same API interface maintained

## Model Methods

### Level Model

```python
level = Level(...)

# Get level type
level_type = level.get_level_type()  # Returns LevelType enum

# Get instrument key
key = level.get_instrument_key()  # Returns unique key

# Calculate prices
stop_loss_price = level.calculate_stop_loss_price()
target_price = level.calculate_target_price()

# Convert to dict
level_dict = level.to_dict()
```

## Service Methods

### LevelService

```python
service = LevelService()

# Save level
success, level, error = service.save_level(
    user_id, index_type, level_value,
    level_uuid=None,  # For updates
    stock_symbol=None,
    stock_exchange=None,
    stop_loss=None,
    target_percentage=None
)

# Get levels
levels = service.get_levels(
    user_id,
    index_type=None,
    today_only=False,
    stock_symbol=None,
    grouped=True
)

# Validate
is_valid, error = service.validate_level(
    level_value,
    current_price=None,
    stop_loss=None,
    target_percentage=None
)
```

## Benefits

1. **Modularity**: Level logic separated from main app
2. **Type Safety**: Models with type hints and enums
3. **Validation**: Built-in validation at service level
4. **Calculations**: Automatic price calculations
5. **Flexibility**: Supports indices and custom stocks
6. **User Scoping**: All operations scoped to user
7. **Testability**: Each component can be tested independently

## Migration Path

### Old Code
```python
from services import save_level, get_levels

save_level(user_id, 'NIFTY_50', 19500.0)
levels = get_levels(user_id, 'NIFTY_50')
```

### New Code
```python
from app.levels import LevelService

service = LevelService()
success, level, error = service.save_level(user_id, 'NIFTY_50', 19500.0, stop_loss=2.0, target_percentage=2.5)
levels = service.get_levels(user_id, 'NIFTY_50', grouped=True)
```

## Next Steps

1. Add level monitoring (price crossing detection)
2. Add level alerts
3. Add level history/audit trail
4. Add bulk operations
5. Add level templates/presets

---

**Last Updated**: November 29, 2025
**Module Version**: 1.0

