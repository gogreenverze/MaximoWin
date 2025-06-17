# Task Planned Materials Documentation

## Overview

This document describes the implementation of Task Planned Materials functionality for work order tasks. The feature provides site-aware planned materials display for tasks with specific statuses (APPR, INPRG, WMATL) using IBM Maximo's MXAPIWODETAIL REST API.

## Problem Statement

The application needed to display planned materials for work order tasks based on:
- Task status (only for APPR, INPRG, WMATL)
- Site-specific material information
- Real-time data from Maximo API
- User-friendly interface integration

## Solution Architecture

### Core Components

1. **TaskPlannedMaterialsService** (`backend/services/task_planned_materials_service.py`)
   - Handles API calls to Maximo MXAPIWODETAIL
   - Provides site-aware material filtering
   - Implements intelligent caching (5-minute timeout)
   - Status-based access control

2. **API Endpoints** (added to `app.py`)
   - `/api/task/<task_wonum>/planned-materials` - Get materials for a task
   - `/api/task/planned-materials/cache/clear` - Clear materials cache
   - `/api/task/planned-materials/cache/stats` - Get cache statistics

3. **Frontend Integration** (`frontend/templates/workorder_detail.html`)
   - Planned materials section for eligible tasks
   - Load materials button with loading states
   - Responsive material display cards
   - Error handling and notifications

## Key Features

### Status-Based Access Control
- **APPR (Approved)**: Shows planned materials
- **INPRG (In Progress)**: Shows planned materials  
- **WMATL (Waiting for Materials)**: Shows planned materials
- **Other statuses**: Materials section not displayed

### Site-Aware Functionality
- Automatically uses user's default site ID
- Filters materials based on site context
- Ensures data relevance for user's location

### Performance Optimization
- 5-minute intelligent caching
- Efficient API calls with proper timeouts
- Lazy loading (materials loaded on demand)
- Minimal impact on existing functionality

### User Experience
- Clean, intuitive interface
- Loading states and progress indicators
- Error handling with user-friendly messages
- Responsive design for all devices

## Technical Implementation

### API Integration

#### Maximo MXAPIWODETAIL Query
```
Endpoint: /oslc/os/mxapiwodetail
Filter: wonum="{task_wonum}" and siteid="{site_id}"
Select: wonum,siteid,wpmaterial.itemnum,wpmaterial.description,wpmaterial.itemqty,wpmaterial.unitcost,wpmaterial.linecost,wpmaterial.storeloc,wpmaterial.itemsetid,wpmaterial.vendor,wpmaterial.directreq
```

#### Data Structure
```python
{
    'itemnum': 'ITEM001',
    'description': 'Material description',
    'itemqty': 5.0,
    'unitcost': 25.50,
    'linecost': 127.50,
    'storeloc': 'STORE01',
    'itemsetid': 'SET001',
    'vendor': 'VENDOR001',
    'directreq': False,
    'unit': 'EA'
}
```

### Frontend Implementation

#### Material Display Card
```html
<div class="material-item">
    <div class="material-header">
        <span class="material-itemnum">ITEM001</span>
        <span class="material-qty">5 EA</span>
    </div>
    <div class="material-description">Material description</div>
    <div class="material-details">
        <!-- Cost and location details -->
    </div>
</div>
```

#### JavaScript API Call
```javascript
fetch(`/api/task/${taskWonum}/planned-materials?status=${taskStatus}`)
    .then(response => response.json())
    .then(data => {
        // Handle materials display
    });
```

## File Structure

### New Files Created
- `backend/services/task_planned_materials_service.py` - Core service (300 lines)
- `TASK_PLANNED_MATERIALS_DOCUMENTATION.md` - This documentation

### Modified Files
- `app.py` - Added API endpoints and service initialization
- `frontend/templates/workorder_detail.html` - Added UI components and JavaScript

## API Endpoints

### GET /api/task/{task_wonum}/planned-materials
**Purpose**: Retrieve planned materials for a specific task

**Parameters**:
- `task_wonum` (path): Work order number of the task
- `status` (query): Current status of the task

**Response**:
```json
{
    "success": true,
    "materials": [
        {
            "itemnum": "ITEM001",
            "description": "Material description",
            "itemqty": 5.0,
            "unitcost": 25.50,
            "linecost": 127.50,
            "storeloc": "STORE01",
            "vendor": "VENDOR001",
            "unit": "EA"
        }
    ],
    "metadata": {
        "load_time": 0.234,
        "source": "api",
        "count": 1
    },
    "show_materials": true,
    "task_wonum": "TASK001",
    "site_id": "LCVKWT"
}
```

### POST /api/task/planned-materials/cache/clear
**Purpose**: Clear the planned materials cache

**Response**:
```json
{
    "success": true,
    "message": "Materials cache cleared"
}
```

### GET /api/task/planned-materials/cache/stats
**Purpose**: Get cache statistics

**Response**:
```json
{
    "success": true,
    "stats": {
        "cache_size": 5,
        "cache_timeout": 300,
        "valid_statuses": ["APPR", "INPRG", "WMATL"]
    }
}
```

## Integration Points

### Existing Functionality Preserved
- All existing work order and task functionality remains unchanged
- Task status updates continue to work as before
- No impact on work order list or details display
- Backward compatibility maintained

### New Feature Integration
- Seamlessly integrated into existing task cards
- Uses existing authentication and session management
- Follows established UI/UX patterns
- Consistent with existing error handling

## Performance Considerations

### Caching Strategy
- 5-minute cache timeout for real-time accuracy
- Cache key: `{task_wonum}_{site_id}`
- Memory-based caching for fast access
- Automatic cache invalidation

### API Optimization
- Efficient OSLC queries with specific field selection
- Proper timeout configuration (5s/30s)
- Error handling with graceful degradation
- Minimal data transfer

### File Size Management
- Service file: 300 lines (within 1000 LOC limit)
- Modular design for maintainability
- Clean separation of concerns
- No code bloat in existing files

## Security Considerations

### Authentication
- Uses existing session-based authentication
- Validates user login status before API calls
- Inherits user permissions and site access

### Data Access
- Site-based filtering ensures data relevance
- No unauthorized access to other sites' data
- Proper error handling without data leakage

## Future Enhancements

### Potential Improvements
1. **Real-time Updates**: WebSocket-based material updates
2. **Material Reservations**: Integration with inventory management
3. **Cost Analysis**: Material cost tracking and reporting
4. **Mobile Optimization**: Enhanced mobile interface
5. **Bulk Operations**: Multiple task material loading

### API Extensions
- Material availability checking
- Vendor information integration
- Material substitution suggestions
- Historical material usage data

## Conclusion

The Task Planned Materials feature provides a comprehensive, site-aware solution for displaying planned materials in work order tasks. The implementation follows best practices for performance, security, and user experience while maintaining full compatibility with existing functionality.

Key benefits:
- ✅ Status-based material access (APPR, INPRG, WMATL)
- ✅ Site-aware data filtering
- ✅ Efficient caching and performance
- ✅ User-friendly interface
- ✅ Seamless integration with existing features
- ✅ Proper error handling and notifications
- ✅ Mobile-responsive design
- ✅ File size discipline (under 1000 LOC)
