# Risk Management Module (Recommended Addition)

```mermaid
flowchart TD
    A[Order Request from BRE] --> B[Risk Management Check]
    B --> C{Max Positions Reached?}
    C -->|Yes| D[Reject Order]
    C -->|No| E{Max Daily Loss Reached?}
    E -->|Yes| D
    E -->|No| F{Position Size Valid?}
    F -->|No| D
    F -->|Yes| G{Max Exposure Limit?}
    G -->|Yes| D
    G -->|No| H{Market Hours Valid?}
    H -->|No| D
    H -->|Yes| I[Approve Order]
    I --> J[Send to OOP]
    D --> K[Notify User/System]
    K --> L[Log Rejection Reason]
    L --> M[End]
    J --> N[End]
    
    style B fill:#e1f5ff
    style I fill:#e1ffe1
    style D fill:#ffe1e1
```

## Risk Management Rules

1. **Position Limits**
   - Maximum number of open positions per instrument
   - Maximum number of total open positions
   - Maximum position size per trade

2. **Loss Limits**
   - Maximum daily loss limit
   - Maximum loss per instrument
   - Maximum drawdown threshold

3. **Exposure Limits**
   - Maximum total exposure
   - Maximum exposure per instrument
   - Maximum leverage

4. **Time-based Rules**
   - Trading hours validation
   - Market close time (3:00 PM)
   - Pre-market and post-market restrictions

