# Levels Expiry System Documentation

## Overview

The levels module supports expiry functionality to control **how long a level should be considered** for trading. This is about the level's validity period, not the instrument's expiry.

## Key Concept

**Level Expiry = How long the level should be considered/active for trading**

- This is independent of the stock/option's expiry
- Determines when the level stops being monitored
- Controls level visibility and consideration in trading logic

## Expiry Types

### 1. Today (`expiry_type: "today"`)
- **Consideration Period**: Only for the day the level was created
- **Expires**: At midnight of the creation date
- **Use Case**: Intraday trading levels that reset daily
- **Example**: Level set today (2025-11-29) expires at 2025-11-29 23:59:59

### 2. Persistent (`expiry_type: "persistent"`)
- **Consideration Period**: Indefinitely (never expires)
- **Expires**: Never
- **Use Case**: Long-term swing trading levels, permanent support/resistance
- **Example**: Level set once, remains active until manually deleted

### 3. Expiry Date (`expiry_type: "expiry_date"`)
- **Consideration Period**: From creation until the specified date
- **Expires**: On the specified date (at end of day)
- **Use Case**: Weekly levels, monthly levels, levels tied to specific events
- **Example**: Level set on 2025-11-29 with expiry_date="2025-12-06" expires on 2025-12-06

## Important Notes

### Level Expiry vs Instrument Expiry

**Level Expiry** (what we're implementing):
- Controls how long the **level itself** is considered
- Independent of the stock/option
- Determines when to stop monitoring this level

**Instrument Expiry** (separate concept):
- When the stock/option contract expires
- Not controlled by level expiry
- Can be different from level expiry

**Example:**
- You set a level for NIFTY 50 option with expiry_date="2025-12-25"
- The level expires on Dec 25 (stops being considered)
- The option might expire on a different date (Dec 26 weekly expiry)
- These are independent

## Database Schema

New columns added to `level` table:
- `expiry_type`: TEXT (default: "today")
  - Values: "today", "persistent", "expiry_date"
- `expiry_date`: TEXT (nullable, ISO date format: YYYY-MM-DD)
  - Required when expiry_type is "expiry_date"
  - Ignored for other expiry types

## API Usage

### Save Level with Expiry

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
**Meaning**: This level will only be considered today. Tomorrow it will be automatically excluded.

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
**Meaning**: This level will be considered indefinitely until manually deleted.

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
**Meaning**: This level will be considered until December 31, 2025. After that date, it will be automatically excluded.

### Get Levels (Active Only - Default)

By default, only levels that should still be considered are returned:

```bash
# Get levels that are still being considered (default)
curl http://localhost:5001/levels/get

# Get all levels including those that should no longer be considered
curl http://localhost:5001/levels/get?active_only=false
```

### Get Expired Levels

```bash
# Get levels that should no longer be considered
curl http://localhost:5001/levels/api/expired
```

### Cleanup Expired Levels

```bash
# Delete levels that have expired
curl -X POST http://localhost:5001/levels/api/cleanup-expired
```

## Use Cases

### 1. Intraday Trading Levels
```json
{
  "expiry_type": "today"
}
```
- Levels reset daily
- Good for day trading
- Automatically excluded tomorrow

### 2. Weekly Trading Levels
```json
{
  "expiry_type": "expiry_date",
  "expiry_date": "2025-12-06"
}
```
- Levels valid for the week
- Set on Monday, expire on Friday
- Automatically excluded after Friday

### 3. Monthly Levels
```json
{
  "expiry_type": "expiry_date",
  "expiry_date": "2025-12-31"
}
```
- Levels valid for the month
- Set at month start, expire at month end
- Automatically excluded after month end

### 4. Long-term Support/Resistance
```json
{
  "expiry_type": "persistent"
}
```
- Levels never expire
- Good for swing trading, long-term positions
- Must be manually deleted when no longer needed

### 5. Event-Based Levels
```json
{
  "expiry_type": "expiry_date",
  "expiry_date": "2025-12-15"
}
```
- Levels tied to specific events (earnings, FOMC, etc.)
- Set before event, expire after event
- Automatically excluded after event date

## Level Model Methods

### Check if Level Should Be Considered

```python
from app.levels import Level

level = Level(...)

# Check if level should still be considered
should_consider = level.is_active()  # Returns True/False

# Check against specific date
from datetime import datetime
check_date = datetime(2025, 12, 1).date()
should_consider = level.is_active(check_date)
```

### Get Consideration Period Info

```python
expiry_info = level.get_expiry_info()
# Returns:
# {
#   'expiry_type': 'today' | 'persistent' | 'expiry_date',
#   'expires': True/False,
#   'expiry_date': '2025-12-31' or None,
#   'is_expired': True/False (for expiry_date type),
#   'description': 'Human-readable description',
#   'consideration_period': 'How long level is considered'
# }
```

## Response Format

Level responses include consideration period information:

```json
{
  "uuid": "abc-123",
  "index_type": "NIFTY_50",
  "level_value": 19500.0,
  "expiry_type": "expiry_date",
  "expiry_date": "2025-12-31",
  "is_active": true,
  "expiry_info": {
    "expiry_type": "expiry_date",
    "expires": true,
    "expiry_date": "2025-12-31",
    "is_expired": false,
    "description": "Level considered until 2025-12-31",
    "consideration_period": "Until 2025-12-31"
  }
}
```

## Automatic Filtering

When retrieving levels:
- **Default behavior**: Only levels that should still be considered are returned
- **Expired levels**: Automatically filtered out (not considered)
- **Override**: Use `active_only=false` to get all levels including expired

## Integration with Trading Logic

When checking if a level should trigger a trade:

```python
from app.levels import LevelService

service = LevelService()

# Get levels that should be considered
levels = service.get_levels(user_id, active_only=True)

# Only these levels will be monitored for price crossings
# Expired levels are automatically excluded
```

## Validation Rules

1. **expiry_type** must be one of: `"today"`, `"persistent"`, `"expiry_date"`
2. **expiry_date** is required when `expiry_type` is `"expiry_date"`
3. **expiry_date** cannot be in the past
4. **expiry_date** must be valid ISO date format (YYYY-MM-DD)

## Migration

Existing levels without expiry information:
- Default to `expiry_type: "today"` (backward compatible)
- Continue to work as before (considered only for today)
- Can be updated to new expiry types

## Database Migration

The expiry columns are automatically added when:
- Repository methods are called
- Database initialization runs
- First level with expiry is saved

No manual migration needed - handled automatically.

## Examples

### Example 1: Daily Reset Levels
```json
{
  "index_type": "BANK_NIFTY",
  "level_value": 43500.0,
  "expiry_type": "today"
}
```
**Behavior**: Level is considered today, automatically excluded tomorrow.

### Example 2: Weekly Levels
```json
{
  "index_type": "NIFTY_50",
  "level_value": 19500.0,
  "expiry_type": "expiry_date",
  "expiry_date": "2025-12-06"
}
```
**Behavior**: Level is considered until Dec 6, then automatically excluded.

### Example 3: Permanent Levels
```json
{
  "index_type": "NIFTY_50",
  "level_value": 19000.0,
  "expiry_type": "persistent"
}
```
**Behavior**: Level is considered indefinitely until manually deleted.

---

**Last Updated**: November 29, 2025
**Feature Version**: 1.0
**Note**: Expiry controls how long the LEVEL is considered, not the instrument's expiry.
