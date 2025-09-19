# Alert Troubleshooting Guide

## Common Error: "Rule condition is already met"

### What This Error Means:
The KITE API is telling you that the alert condition you're trying to set is already true. For example:
- If NIFTY BANK is currently at ₹25,500 and you set an alert for "Above ₹25,342", the condition is already met
- If NIFTY 50 is at ₹24,200 and you set an alert for "Below ₹24,500", the condition is already met

### How to Fix This:

#### 1. **Check Current Prices**
- Look at the current prices displayed on the prices page
- The form now shows current prices as hints to help you set appropriate targets

#### 2. **Set Realistic Targets**
- **For "Above" alerts**: Set target price higher than current price
- **For "Below" alerts**: Set target price lower than current price
- **For "% Up" alerts**: The system calculates the target price automatically
- **For "% Down" alerts**: The system calculates the target price automatically

#### 3. **Example Scenarios**

**Scenario 1: NIFTY BANK at ₹25,500**
- ❌ **Wrong**: "Above ₹25,342" (already above)
- ✅ **Correct**: "Above ₹25,600" (realistic target)
- ✅ **Correct**: "Below ₹25,400" (support level)

**Scenario 2: NIFTY 50 at ₹24,200**
- ❌ **Wrong**: "Below ₹24,500" (already below)
- ✅ **Correct**: "Above ₹24,300" (resistance level)
- ✅ **Correct**: "Below ₹24,100" (support level)

### 4. **Smart Tips**

#### **Use Percentage-Based Alerts**
- Instead of guessing prices, use percentage changes
- "2% Up" from ₹25,500 = ₹26,010 (automatically calculated)
- "1.5% Down" from ₹25,500 = ₹25,117.50 (automatically calculated)

#### **Set Multiple Alerts**
- Create alerts for different scenarios
- Example: "Above ₹26,000" AND "Below ₹25,000"
- This covers both breakout and breakdown scenarios

#### **Use Support/Resistance Levels**
- Set alerts at key technical levels
- Round numbers often act as support/resistance
- Example: ₹25,000, ₹25,500, ₹26,000

### 5. **Form Features to Help You**

The prices page now includes:
- **Current Price Hints**: Shows current price when you select symbol and condition
- **Smart Validation**: Prevents invalid inputs
- **Real-time Updates**: Prices update every second

### 6. **Example Workflow**

1. **Check Current Price**: Look at NIFTY BANK price (e.g., ₹25,500)
2. **Choose Condition**: Select "Above" or "Below"
3. **Set Target**: Enter a realistic target (e.g., ₹25,600 for "Above")
4. **Name Alert**: Give it a descriptive name (e.g., "NIFTY BANK Breakout")
5. **Create Alert**: Click "Create" button

### 7. **Common Mistakes to Avoid**

- ❌ Setting target equal to current price
- ❌ Setting "Above" target below current price
- ❌ Setting "Below" target above current price
- ❌ Using unrealistic targets (too close to current price)

### 8. **If You Still Get Errors**

1. **Refresh the page** to get latest prices
2. **Check if prices have moved** significantly
3. **Try a different target price** with more margin
4. **Use percentage-based alerts** instead of absolute prices

### 9. **Testing Your Alert**

Before creating the alert:
1. Note the current price
2. Calculate your target price
3. Verify the condition makes sense
4. Create the alert

### 10. **Example Calculations**

**Current NIFTY BANK: ₹25,500**

| Condition | Target | Result | Valid? |
|-----------|--------|--------|--------|
| Above | ₹25,400 | Already above | ❌ |
| Above | ₹25,600 | Will trigger when price rises | ✅ |
| Below | ₹25,600 | Already below | ❌ |
| Below | ₹25,400 | Will trigger when price falls | ✅ |
| 2% Up | 2% | Target: ₹26,010 | ✅ |
| 1% Down | 1% | Target: ₹25,245 | ✅ |

Remember: The key is to set targets that are **realistic** and **not already met** by the current market conditions.
