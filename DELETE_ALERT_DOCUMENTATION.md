# Delete Alert API Documentation

This document describes the delete alert functionality that allows you to remove alerts from both the KITE API and local database.

## Overview

The delete alert functionality provides:
- Delete alerts from KITE API
- Remove alerts from local database
- Proper error handling and validation
- User-friendly interface integration

## API Endpoint

### Delete Alert

**Endpoint:** `DELETE /alerts/delete/<uuid>`

**Description:** Deletes an alert by its UUID from both KITE API and local database.

**Parameters:**
- `uuid` (path parameter): The unique identifier of the alert to delete

**Headers:**
```
Content-Type: application/json
```

**Authentication:** Required (must be logged in)

**Response:**

**Success (200):**
```json
{
    "message": "Alert deleted successfully",
    "success": true
}
```

**Error Responses:**

**Unauthorized (401):**
```json
{
    "error": "Not authenticated"
}
```

**Server Error (500):**
```json
{
    "error": "Failed to delete alert: [KITE API error message]"
}
```

## Usage Examples

### Using curl

```bash
# Delete an alert by UUID
curl -X DELETE http://localhost:5001/alerts/delete/b88f3994-4d51-4266-b7d4-85ac2e2f7212
```

### Using Python requests

```python
import requests

# Delete an alert
uuid = "b88f3994-4d51-4266-b7d4-85ac2e2f7212"
response = requests.delete(f"http://localhost:5001/alerts/delete/{uuid}")

if response.status_code == 200:
    result = response.json()
    print("Alert deleted successfully!")
else:
    print(f"Error: {response.json()}")
```

### Using JavaScript fetch

```javascript
// Delete an alert
const uuid = "b88f3994-4d51-4266-b7d4-85ac2e2f7212";

fetch(`/alerts/delete/${uuid}`, {
    method: 'DELETE',
    headers: {
        'Content-Type': 'application/json',
    }
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        console.log('Alert deleted successfully!');
    } else {
        console.error('Error:', data.error);
    }
})
.catch(error => {
    console.error('Error:', error);
});
```

## Web Interface Integration

### Prices Page Integration

The delete functionality is integrated into the prices page:

1. **Alert List Display**: Shows all stored alerts with delete buttons
2. **Delete Button**: Each alert has a "Delete" button
3. **Confirmation Dialog**: Asks for confirmation before deletion
4. **Loading State**: Shows "Deleting..." during the process
5. **Real-time Updates**: Removes alert from display after successful deletion

### User Experience Flow

1. **User clicks "Delete"** on an alert
2. **Confirmation dialog** appears: "Are you sure you want to delete this alert?"
3. **User confirms** deletion
4. **Button shows "Deleting..."** and becomes disabled
5. **API call** is made to delete the alert
6. **Success**: Alert is removed from display and database
7. **Error**: User sees error message, button is re-enabled

## Error Handling

### Common Error Scenarios

1. **Authentication Required**
   - Error: 401 Unauthorized
   - Solution: Login first at `/login`

2. **Alert Not Found**
   - Error: 500 with KITE API error
   - Solution: Alert may have been deleted already

3. **Network Issues**
   - Error: Connection timeout
   - Solution: Check internet connection and KITE API status

4. **Invalid UUID**
   - Error: 500 with validation error
   - Solution: Use a valid alert UUID

### Error Messages

The system provides user-friendly error messages:

- **"Not authenticated"** - User needs to login
- **"Failed to delete alert: [details]"** - KITE API error
- **"Error deleting alert: [details]"** - System error

## Database Integration

### Local Database Cleanup

When an alert is successfully deleted from KITE API:

1. **KITE API deletion** is confirmed (status 200)
2. **Local database cleanup** is performed
3. **Alert record** is removed from `alerts` table
4. **Success confirmation** is logged

### Database Function

```python
def delete_alert_from_database(uuid):
    """Delete alert from local database"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM alerts WHERE uuid = ?', (uuid,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"Alert deleted from database: {uuid}")
        else:
            print(f"Alert not found in database: {uuid}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error deleting alert from database: {e}")
        return False
```

## Testing

### Test Script

Run the delete alert test:

```bash
python test_delete_alert.py
```

This will test:
- Deleting existing alerts
- Error handling for non-existent alerts
- Authentication validation
- Database cleanup verification

### Manual Testing

1. **Create an alert** using the prices page
2. **Note the alert details** (name, condition, etc.)
3. **Click the "Delete" button**
4. **Confirm deletion** in the dialog
5. **Verify alert is removed** from the list
6. **Check database** to confirm removal

## Security Considerations

### Authentication

- All delete operations require valid authentication
- Session must be active with valid access token
- API credentials must be properly configured

### Authorization

- Users can only delete their own alerts
- UUID-based access control prevents unauthorized deletions
- KITE API validates user permissions

### Data Integrity

- Deletion is atomic (both KITE and local database)
- If KITE deletion fails, local database is not modified
- Proper error handling prevents partial deletions

## Best Practices

### For Users

1. **Confirm before deleting** - Use the confirmation dialog
2. **Check alert details** - Make sure you're deleting the right alert
3. **Verify deletion** - Check that the alert is removed from the list

### For Developers

1. **Handle errors gracefully** - Provide meaningful error messages
2. **Validate inputs** - Check UUID format and authentication
3. **Log operations** - Track successful and failed deletions
4. **Test thoroughly** - Verify both API and database operations

## Troubleshooting

### Common Issues

1. **"Alert not found"**
   - Alert may have been deleted already
   - Check if UUID is correct
   - Verify alert exists in stored alerts

2. **"Authentication required"**
   - Login again at `/login`
   - Check if session has expired
   - Verify API credentials

3. **"Failed to delete alert"**
   - Check KITE API status
   - Verify internet connection
   - Check if alert exists in KITE system

### Debug Steps

1. **Check stored alerts**: `GET /alerts/stored`
2. **Verify authentication**: `GET /session/status`
3. **Test with curl**: Use direct API calls
4. **Check logs**: Look for error messages in console

## Integration Notes

### KITE API Integration

- Uses KITE API v3 for deletion
- Proper headers and authentication
- Handles KITE API response codes
- Maintains consistency with KITE system

### Local Database Sync

- Keeps local database in sync with KITE
- Removes orphaned records
- Maintains data integrity
- Provides offline reference

The delete alert functionality provides a complete solution for managing alerts with proper error handling, user experience, and data integrity.
