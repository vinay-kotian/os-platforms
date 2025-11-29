# Modular Architecture Design - OS Platforms Trading System

## Table of Contents
1. [Overview](#overview)
2. [Current Problems](#current-problems)
3. [Proposed Architecture](#proposed-architecture)
4. [Module Breakdown](#module-breakdown)
5. [Directory Structure](#directory-structure)
6. [Dependency Flow](#dependency-flow)
7. [Data Flow](#data-flow)
8. [Benefits of Modularization](#benefits-of-modularization)
9. [Migration Strategy](#migration-strategy)

---

## Overview

This document outlines a modular architecture design for rewriting the OS Platforms Trading System. The goal is to transform the current monolithic structure into a clean, maintainable, and testable codebase.

### Current State
- **app.py**: 1125 lines - Contains all Flask routes, request handling, and business logic
- **services.py**: 3000+ lines - Contains all business logic, database operations, WebSocket handling, trading logic, alerts, etc.
- **Tight Coupling**: Everything is interconnected with global variables
- **Hard to Test**: Business logic mixed with infrastructure code
- **Hard to Maintain**: Changes in one area affect multiple areas

### Target State
- **Separation of Concerns**: Clear boundaries between layers
- **Single Responsibility**: Each module has one clear purpose
- **Dependency Injection**: Loose coupling between components
- **Testability**: Each module can be tested independently
- **Scalability**: Easy to add new features or modify existing ones

---

## Current Problems

### 1. **Monolithic Structure**
- All business logic in `services.py` (3000+ lines)
- All routes in `app.py` (1125 lines)
- No clear separation of concerns

### 2. **Global State**
- Global variables scattered throughout (`kite`, `websocket_prices`, `order_placed_at_level`, etc.)
- Hard to track state changes
- Difficult to test
- Race conditions possible

### 3. **Tight Coupling**
- Direct imports between modules
- Hard-coded dependencies
- Difficult to swap implementations

### 4. **Mixed Responsibilities**
- Database operations mixed with business logic
- WebSocket handling mixed with trading logic
- API routes mixed with business logic

### 5. **Testing Challenges**
- Can't test business logic without Flask app
- Can't test database operations without real database
- Can't test WebSocket without real connection

---

## Proposed Architecture

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                      │
│  (Flask Routes, Templates, Static Files)                │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  API/Controller Layer                    │
│  (Request Validation, Response Formatting)              │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  Service/Business Logic Layer            │
│  (Trading Logic, Alert Logic, Level Management)         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  Data Access Layer                       │
│  (Repository Pattern, Database Operations)               │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  External Integration Layer              │
│  (Zerodha API, WebSocket, Third-party Services)         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  Infrastructure Layer                    │
│  (Configuration, Logging, Error Handling)                │
└──────────────────────────────────────────────────────────┘
```

---

## Module Breakdown

### 1. **Core Application Module** (`app/`)
**Purpose**: Application initialization and configuration

**Components**:
- `__init__.py`: Flask app factory, dependency injection setup
- `config.py`: Configuration management (dev, prod, test)
- `extensions.py`: Flask extensions initialization (SocketIO, etc.)
- `middleware.py`: Request/response middleware

**Responsibilities**:
- Initialize Flask application
- Configure logging
- Set up dependency injection container
- Register blueprints
- Initialize background workers

---

### 2. **API/Controller Module** (`app/api/`)
**Purpose**: HTTP request handling and response formatting

**Structure**:
```
app/api/
├── __init__.py
├── auth/
│   ├── __init__.py
│   ├── routes.py          # Login, logout, callback routes
│   └── schemas.py         # Request/response validation
├── trading/
│   ├── __init__.py
│   ├── routes.py          # Trading endpoints
│   └── schemas.py
├── levels/
│   ├── __init__.py
│   ├── routes.py          # Level management endpoints
│   └── schemas.py
├── alerts/
│   ├── __init__.py
│   ├── routes.py          # Alert management endpoints
│   └── schemas.py
└── prices/
    ├── __init__.py
    ├── routes.py          # Price endpoints
    └── schemas.py
```

**Responsibilities**:
- Parse and validate HTTP requests
- Call appropriate service methods
- Format HTTP responses
- Handle errors and return appropriate status codes
- **NO business logic** - delegates to services

---

### 3. **Service Layer** (`app/services/`)
**Purpose**: Business logic implementation

**Structure**:
```
app/services/
├── __init__.py
├── trading/
│   ├── __init__.py
│   ├── trade_service.py       # Trade execution logic
│   ├── level_monitor.py        # Level monitoring logic
│   ├── trend_detector.py      # Trend detection logic
│   └── order_executor.py      # Order placement logic
├── alerts/
│   ├── __init__.py
│   ├── alert_service.py       # Alert management
│   └── alert_trigger.py        # Alert triggering logic
├── prices/
│   ├── __init__.py
│   └── price_service.py        # Price data management
└── auth/
    ├── __init__.py
    └── auth_service.py         # Authentication logic
```

**Responsibilities**:
- Implement business rules
- Coordinate between repositories and external services
- Handle business logic validation
- **NO direct database access** - uses repositories
- **NO HTTP concerns** - pure business logic

---

### 4. **Repository Layer** (`app/repositories/`)
**Purpose**: Data access abstraction

**Structure**:
```
app/repositories/
├── __init__.py
├── base_repository.py          # Base class with common methods
├── level_repository.py         # Level CRUD operations
├── trade_repository.py         # Trade CRUD operations
├── alert_repository.py         # Alert CRUD operations
├── entry_price_repository.py   # Entry price operations
└── interfaces.py               # Repository interfaces
```

**Responsibilities**:
- Abstract database operations
- Provide clean interface for data access
- Handle SQL queries
- Return domain models, not raw database rows
- **NO business logic** - pure data access

---

### 5. **Models/Domain Layer** (`app/models/`)
**Purpose**: Domain entities and data structures

**Structure**:
```
app/models/
├── __init__.py
├── level.py                    # Level domain model
├── trade.py                    # Trade domain model
├── paper_trade.py              # Paper trade domain model
├── alert.py                    # Alert domain model
├── price.py                    # Price data model
└── user.py                     # User/session model
```

**Responsibilities**:
- Define domain entities
- Business rules validation
- Data structure definitions
- **NO database concerns** - pure domain logic

---

### 6. **External Integration Layer** (`app/integrations/`)
**Purpose**: External service integrations

**Structure**:
```
app/integrations/
├── __init__.py
├── zerodha/
│   ├── __init__.py
│   ├── kite_client.py          # KiteConnect wrapper
│   ├── websocket_client.py     # WebSocket connection
│   ├── alert_client.py         # Alert API client
│   └── order_client.py         # Order placement client
└── interfaces.py                # Integration interfaces
```

**Responsibilities**:
- Wrap external APIs
- Handle connection management
- Error handling and retries
- Rate limiting
- **NO business logic** - pure integration

---

### 7. **Background Workers** (`app/workers/`)
**Purpose**: Background task execution

**Structure**:
```
app/workers/
├── __init__.py
├── price_monitor.py            # Price monitoring worker
├── trade_monitor.py            # Trade monitoring worker
├── level_monitor.py            # Level monitoring worker
├── alert_monitor.py            # Alert monitoring worker
└── worker_manager.py           # Worker lifecycle management
```

**Responsibilities**:
- Run background tasks
- Monitor prices
- Execute trades
- Check alerts
- **Isolated from main application** - can be run separately

---

### 8. **WebSocket Module** (`app/websocket/`)
**Purpose**: Real-time communication

**Structure**:
```
app/websocket/
├── __init__.py
├── handlers.py                 # SocketIO event handlers
├── price_broadcaster.py        # Price update broadcasting
└── connection_manager.py       # Connection management
```

**Responsibilities**:
- Handle WebSocket connections
- Broadcast price updates
- Manage client connections
- **Separate from HTTP routes**

---

### 9. **Utilities** (`app/utils/`)
**Purpose**: Shared utilities and helpers

**Structure**:
```
app/utils/
├── __init__.py
├── validators.py               # Input validation
├── formatters.py               # Data formatting
├── exceptions.py               # Custom exceptions
├── decorators.py               # Common decorators
└── helpers.py                  # Helper functions
```

**Responsibilities**:
- Reusable utility functions
- Common validations
- Formatting helpers
- **No dependencies on other modules**

---

### 10. **Configuration** (`app/config/`)
**Purpose**: Configuration management

**Structure**:
```
app/config/
├── __init__.py
├── settings.py                 # Base settings
├── development.py              # Dev environment
├── production.py               # Prod environment
└── testing.py                  # Test environment
```

**Responsibilities**:
- Environment-specific configuration
- Feature flags
- Constants
- **Centralized configuration**

---

## Directory Structure

```
os-platforms/
├── app/                        # Main application package
│   ├── __init__.py            # App factory
│   ├── config/                # Configuration
│   ├── api/                   # API routes/controllers
│   │   ├── auth/
│   │   ├── trading/
│   │   ├── levels/
│   │   ├── alerts/
│   │   └── prices/
│   ├── services/              # Business logic
│   │   ├── trading/
│   │   ├── alerts/
│   │   ├── prices/
│   │   └── auth/
│   ├── repositories/          # Data access
│   ├── models/                # Domain models
│   ├── integrations/          # External services
│   │   └── zerodha/
│   ├── workers/               # Background workers
│   ├── websocket/             # WebSocket handling
│   ├── utils/                 # Utilities
│   └── middleware/            # Middleware
│
├── tests/                     # Test suite
│   ├── unit/                  # Unit tests
│   │   ├── services/
│   │   ├── repositories/
│   │   └── integrations/
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
│
├── migrations/                # Database migrations
│   └── versions/
│
├── scripts/                   # Utility scripts
│   ├── setup_db.py
│   ├── seed_data.py
│   └── run_workers.py
│
├── docs/                      # Documentation
│   ├── api/
│   ├── architecture/
│   └── guides/
│
├── templates/                 # HTML templates
├── static/                    # Static assets
│   ├── css/
│   ├── js/
│   └── images/
│
├── requirements.txt           # Dependencies
├── requirements-dev.txt       # Dev dependencies
├── .env.example               # Environment template
├── .gitignore
├── README.md
└── run.py                     # Application entry point
```

---

## Dependency Flow

### Dependency Rules

1. **API Layer** → **Service Layer** → **Repository Layer** → **Database**
2. **Service Layer** → **Integration Layer** → **External APIs**
3. **Workers** → **Service Layer** (same as API)
4. **WebSocket** → **Service Layer** (same as API)
5. **Models** are used by all layers (no dependencies)

### Dependency Injection

**Example Flow**:
```
API Route → Service (injected) → Repository (injected) → Database
         → Integration (injected) → External API
```

**Benefits**:
- Easy to mock for testing
- Can swap implementations
- Clear dependencies

---

## Data Flow

### Price Update Flow

```
1. Zerodha WebSocket → Integration Layer (websocket_client)
   ↓
2. Integration Layer → Service Layer (price_service)
   ↓
3. Service Layer → Repository Layer (price_repository) [optional - cache]
   ↓
4. Service Layer → WebSocket Module (broadcast to clients)
   ↓
5. Service Layer → Workers (trigger level monitoring)
   ↓
6. Workers → Service Layer (check levels)
   ↓
7. Service Layer → Integration Layer (place orders if needed)
```

### Trade Execution Flow

```
1. API Route (POST /trading/execute)
   ↓
2. Controller validates request
   ↓
3. Controller → Service (trade_service.execute_trade)
   ↓
4. Service → Repository (trade_repository.create)
   ↓
5. Service → Integration (order_client.place_order)
   ↓
6. Service → Repository (trade_repository.update_status)
   ↓
7. Controller returns response
```

---

## Benefits of Modularization

### 1. **Maintainability**
- Clear separation of concerns
- Easy to locate code
- Changes isolated to specific modules

### 2. **Testability**
- Each module can be tested independently
- Easy to mock dependencies
- Unit tests for business logic
- Integration tests for API

### 3. **Scalability**
- Easy to add new features
- Can scale workers independently
- Can add new integrations easily

### 4. **Reusability**
- Services can be reused by API and workers
- Repositories can be reused across services
- Utilities shared across modules

### 5. **Team Collaboration**
- Multiple developers can work on different modules
- Clear ownership boundaries
- Reduced merge conflicts

### 6. **Debugging**
- Easier to trace issues
- Clear error boundaries
- Better logging structure

---

## Migration Strategy

### Phase 1: Foundation (Week 1-2)
1. Set up new directory structure
2. Create base classes and interfaces
3. Set up dependency injection
4. Create configuration management

### Phase 2: Data Layer (Week 2-3)
1. Create repository interfaces
2. Implement repositories
3. Create domain models
4. Migrate database operations

### Phase 3: Service Layer (Week 3-4)
1. Extract business logic to services
2. Implement trading services
3. Implement alert services
4. Implement price services

### Phase 4: Integration Layer (Week 4-5)
1. Create Zerodha integration wrapper
2. Implement WebSocket client
3. Implement API clients
4. Add error handling and retries

### Phase 5: API Layer (Week 5-6)
1. Create API routes/controllers
2. Implement request validation
3. Wire up services
4. Add error handling

### Phase 6: Workers (Week 6-7)
1. Extract background workers
2. Implement worker manager
3. Add monitoring and health checks

### Phase 7: Testing & Refinement (Week 7-8)
1. Write unit tests
2. Write integration tests
3. Performance testing
4. Bug fixes and optimization

---

## Key Design Principles

### 1. **Single Responsibility Principle**
Each module/class has one reason to change

### 2. **Dependency Inversion**
Depend on abstractions, not concretions

### 3. **Interface Segregation**
Small, focused interfaces

### 4. **Open/Closed Principle**
Open for extension, closed for modification

### 5. **Don't Repeat Yourself (DRY)**
Shared utilities and base classes

### 6. **Separation of Concerns**
Clear boundaries between layers

---

## Module Communication Patterns

### 1. **Request-Response (Synchronous)**
- API → Service → Repository
- Used for immediate operations

### 2. **Event-Driven (Asynchronous)**
- WebSocket → Event Bus → Workers
- Used for real-time updates

### 3. **Observer Pattern**
- Price updates → Notify subscribers
- Used for monitoring

### 4. **Strategy Pattern**
- Different trading strategies
- Used for extensibility

---

## State Management

### Current Problem
- Global variables everywhere
- Hard to track state
- Race conditions

### Proposed Solution

**1. Dependency Injection Container**
- Centralized state management
- Lifecycle management
- Easy to test

**2. Repository Pattern**
- Database state in repositories
- Cached state in services
- Clear ownership

**3. Event Sourcing (Optional)**
- Track all state changes
- Replay events for debugging
- Audit trail

---

## Error Handling Strategy

### 1. **Custom Exceptions**
```
app/exceptions/
├── trading_exceptions.py
├── integration_exceptions.py
└── validation_exceptions.py
```

### 2. **Error Handling Middleware**
- Centralized error handling
- Consistent error responses
- Logging

### 3. **Retry Logic**
- In integration layer
- Configurable retry policies
- Circuit breaker pattern

---

## Logging Strategy

### 1. **Structured Logging**
- JSON format for production
- Human-readable for development
- Contextual information

### 2. **Log Levels by Module**
- API: INFO for requests, ERROR for failures
- Services: DEBUG for business logic
- Integrations: WARN for retries, ERROR for failures

### 3. **Log Aggregation**
- Centralized logging
- Searchable logs
- Alerting on errors

---

## Testing Strategy

### 1. **Unit Tests**
- Test each service independently
- Mock dependencies
- Fast execution

### 2. **Integration Tests**
- Test API endpoints
- Test database operations
- Test external integrations (mocked)

### 3. **End-to-End Tests**
- Test complete workflows
- Use test database
- Test with real integrations (sandbox)

---

## Configuration Management

### 1. **Environment Variables**
- `.env` files for local development
- Environment variables for production
- Secrets management

### 2. **Feature Flags**
- Enable/disable features
- A/B testing
- Gradual rollouts

### 3. **Configuration Classes**
- Type-safe configuration
- Validation on startup
- Default values

---

## Performance Considerations

### 1. **Caching Strategy**
- Cache frequently accessed data
- Invalidate on updates
- Redis for distributed caching

### 2. **Database Optimization**
- Indexes on frequently queried columns
- Connection pooling
- Query optimization

### 3. **Async Operations**
- Background workers for heavy operations
- Async API endpoints where possible
- Non-blocking I/O

---

## Security Considerations

### 1. **Authentication & Authorization**
- Separate auth module
- Token management
- Role-based access control

### 2. **Input Validation**
- Validate at API layer
- Sanitize inputs
- Prevent SQL injection

### 3. **Secrets Management**
- Never commit secrets
- Use environment variables
- Rotate credentials regularly

---

## Monitoring & Observability

### 1. **Health Checks**
- `/health` endpoint
- Database connectivity
- External service status

### 2. **Metrics**
- Request counts
- Response times
- Error rates
- Trade execution metrics

### 3. **Tracing**
- Request tracing
- Performance profiling
- Debug information

---

## Conclusion

This modular architecture provides:

✅ **Clear separation of concerns**
✅ **Easy to test and maintain**
✅ **Scalable and extensible**
✅ **Team-friendly structure**
✅ **Production-ready patterns**

The migration can be done incrementally, allowing the system to continue operating while being refactored. Each module can be developed and tested independently, reducing risk and allowing for parallel development.

---

**Next Steps:**
1. Review and approve architecture
2. Set up project structure
3. Begin Phase 1 implementation
4. Establish coding standards and guidelines
5. Set up CI/CD pipeline

---

**Last Updated**: November 28, 2025
**Version**: 1.0

