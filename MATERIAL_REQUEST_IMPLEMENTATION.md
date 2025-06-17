# Material Request Implementation

## Overview
This document describes the implementation of material request functionality for work orders, allowing users to search inventory and add material requests directly from the work order details page.

## Features Implemented

### 1. Enhanced Inventory Search Modal
- **File**: `frontend/templates/components/inventory_search_modal.html`
- **Added**: Material Request Modal for collecting request details
- **Features**:
  - Selected item information display
  - Quantity input with validation
  - Location input (optional for direct requests)
  - Direct request checkbox
  - Notes field for additional comments
  - Responsive design with Bootstrap styling

### 2. Updated Inventory Search JavaScript
- **File**: `frontend/static/js/inventory_search.js`
- **Added**: 
  - "Add to Request" buttons on each inventory item card
  - `MaterialRequestManager` class for handling request form
  - Form validation and submission logic
  - Success/error message handling
  - Integration with existing inventory search functionality

### 3. Backend Material Request Service
- **File**: `backend/services/material_request_service.py`
- **Based on**: `successful_material_addition.py` model
- **Features**:
  - Session-based authentication using token manager
  - Work order validation
  - Item validation for site
  - AddChange payload construction following Maximo API requirements
  - Direct request vs location-based request handling
  - Proper error handling and logging

### 4. API Endpoint
- **File**: `app.py`
- **Endpoint**: `POST /api/workorder/add-material-request`
- **Features**:
  - Session validation
  - Request data validation
  - Integration with MaterialRequestService
  - Comprehensive error handling
  - Logging for debugging

## Implementation Details

### Material Request Flow
1. User clicks "Search Inventory" on work order details page
2. User searches for items using the inventory search modal
3. User clicks "Add to Request" on desired item
4. Material request form opens with pre-populated item details
5. User fills in quantity, location (optional), and notes
6. User submits the request
7. Backend validates and adds material to work order using MXAPIWODETAIL API
8. Success/error message displayed to user

### API Payload Structure
Following the `successful_material_addition.py` model and memory guidance:

```json
{
  "_action": "AddChange",
  "wonum": "2021-1234567",
  "siteid": "TESTSITE",
  "description": "Work Order Description",
  "status": "APPR",
  "assetnum": "ASSET001",
  "location": "LOCATION001",
  "wpmaterial": [{
    "itemnum": "ITEM001",
    "itemqty": 2.0,
    "directreq": true,  // true for direct request, false for location-based
    "requestby": "USERNAME",
    "location": "LOCATION001",  // only included if directreq=false
    "remarks": "Optional notes"
  }]
}
```

### Key Implementation Points

#### Direct Request vs Location-Based Request
- **Direct Request** (`directreq=true`): No location required, material requested directly
- **Location-Based Request** (`directreq=false`): Location must be specified

#### Memory Guidance Compliance
- For `directreq=1` (checked): payload excludes location and sets `directreq=1`
- For `directreq=0` (unchecked): payload includes location and sets `directreq=0`
- All payload values are dynamic and related to current record including `siteid`
- No hardcoded values in API payloads

#### Session Management
- Uses existing Flask session with MaximoTokenManager
- Validates session before processing requests
- Leverages existing authentication infrastructure

## Files Modified/Created

### New Files
- `backend/services/material_request_service.py` - Material request service
- `test_material_request.py` - Test script for validation
- `MATERIAL_REQUEST_IMPLEMENTATION.md` - This documentation

### Modified Files
- `frontend/templates/components/inventory_search_modal.html` - Added material request modal
- `frontend/static/js/inventory_search.js` - Added request functionality
- `app.py` - Added API endpoint and service initialization

## Testing
- Unit tests created in `test_material_request.py`
- Tests cover service initialization, API mocking, and payload structure
- All tests pass successfully

## Usage Instructions

### For Users
1. Navigate to work order details page
2. Click "Search Inventory" button (available for tasks in APPR, ASSIGN, WMATL, INPRG status)
3. Search for desired items
4. Click "Add to Request" on the item you want to request
5. Fill in the material request form:
   - Quantity (required)
   - Location (optional, leave blank for direct request)
   - Check/uncheck "Direct Request" as needed
   - Add notes if desired
6. Click "Submit Request"
7. Wait for confirmation message

### For Developers
- Service follows the successful_material_addition.py model
- Uses existing session management and authentication
- Integrates with existing inventory search functionality
- Follows established error handling patterns
- Maintains consistency with existing API patterns

## Error Handling
- Form validation on frontend
- Session validation on backend
- Work order existence validation
- Item validation for site
- Quantity validation
- Comprehensive error messages
- Logging for debugging

## Future Enhancements
- Bulk material requests
- Material request history
- Request approval workflow
- Integration with procurement systems
- Advanced search filters
- Material availability checking
