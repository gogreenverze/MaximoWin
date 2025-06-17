# Inventory Search Implementation

## Overview
This document describes the implementation of the new **Inventory Search** functionality for the Work Order Details page. The feature allows users to search inventory items using MXAPIINVENTORY and MXAPIITEM APIs with comprehensive data display.

## Requirements Fulfilled
✅ **New Button**: Added "Search Inventory" button next to "Load Materials"  
✅ **Status Visibility**: Button only visible when task status is in (APPR, ASSIGN, WMATL, INPRG)  
✅ **Search Functionality**: Search by ITEMNUM (partial/full) and DESCRIPTION (partial/full)  
✅ **Data Sources**: Primary MXAPIINVENTORY, Secondary MXAPIITEM for missing fields  
✅ **Site Filtering**: Automatically filters by current work order's SITEID  
✅ **Real Data Only**: No mock/fake data - only real Maximo data  
✅ **Mobile Responsive**: Fully responsive design for all devices  
✅ **Clean Display**: Neat, organized display of all requested fields  

## Architecture

### Backend Components

#### 1. InventorySearchService (`backend/services/inventory_search_service.py`)
**Purpose**: Core service for inventory search functionality

**Key Features**:
- Two-stage search strategy (MXAPIINVENTORY → MXAPIITEM enhancement)
- Site-aware filtering using current work order SITEID
- Intelligent caching (5-minute timeout)
- Comprehensive error handling
- Real-time data processing

**Main Methods**:
- `search_inventory_items()` - Primary search method
- `_search_inventory_primary()` - MXAPIINVENTORY search
- `_enhance_with_item_data()` - MXAPIITEM data enhancement
- `_get_item_details()` - Individual item details from MXAPIITEM

#### 2. API Endpoints (`app.py`)
**New Endpoints Added**:
- `GET /api/inventory/search` - Main search endpoint
- `GET /api/inventory/item-details/<itemnum>` - Item details
- `POST /api/inventory/cache/clear` - Clear search cache
- `GET /api/inventory/cache/stats` - Cache statistics

### Frontend Components

#### 1. Inventory Search Modal (`frontend/templates/components/inventory_search_modal.html`)
**Features**:
- Bootstrap modal with responsive design
- Search form with term input and limit selection
- Real-time search results display
- Mobile-optimized card layout
- Search statistics and performance info

#### 2. JavaScript Manager (`frontend/static/js/inventory_search.js`)
**Class**: `InventorySearchManager`

**Key Features**:
- Real-time search with debouncing (500ms)
- Responsive UI management
- Search term highlighting
- Currency formatting
- Error handling and loading states

#### 3. Template Integration (`frontend/templates/workorder_detail.html`)
**Changes Made**:
- Added "Search Inventory" button with status-based visibility
- Included inventory search modal
- Integrated JavaScript functionality

## Data Fields Displayed

### From MXAPIINVENTORY:
- **LOCATION** - Storage location
- **ITEMNUM** - Item number
- **SITEID** - Site identifier
- **ISSUEUNIT** - Issue unit of measure
- **ORDERUNIT** - Order unit of measure
- **CURBALTOTAL** - Current balance total
- **AVBLBALANCE** - Available balance
- **AVGCOST** - Average cost (from invcost)
- **LASTCOST** - Last cost (from invcost)
- **STDCOST** - Standard cost (from invcost)

### From MXAPIITEM (Enhancement):
- **ITEMNUM** - Item number
- **DESCRIPTION** - Item description
- **ISSUEUNIT** - Issue unit
- **ORDERUNIT** - Order unit
- **CONDITIONCODE** - Condition code
- **ITEMSETID** - Item set identifier
- **NSN** - National Stock Number
- **COMMODITYGROUP** - Commodity group
- **COMMODITY** - Commodity classification

## Search Strategy

### 1. Primary Search (MXAPIINVENTORY)
```sql
-- Search filters applied:
(itemnum="{search_term}" OR itemnum~"{search_term}" OR description~"{search_term}")
AND siteid="{current_siteid}" 
AND status="ACTIVE"
```

### 2. Data Enhancement (MXAPIITEM)
For each item found in inventory, fetch additional details from MXAPIITEM:
```sql
itemnum="{itemnum}" AND status="ACTIVE"
```

### 3. Cost Data Processing
Processes `invcost` related table data for:
- Average cost (AVERAGE cost type)
- Last cost (LAST cost type)  
- Standard cost (STANDARD cost type)
- Currency information

## User Interface

### Button Placement
- Located next to "Load Materials" button
- Only visible when task status is in: APPR, ASSIGN, WMATL, INPRG
- Green outline styling to distinguish from materials button

### Search Modal
- **Header**: Search form with term input and limit selection
- **Body**: Dynamic results display with loading states
- **Footer**: Search statistics and close button

### Results Display
- **Card Layout**: Each item displayed in responsive card
- **Header Section**: Item number, location, site, status badge
- **Body Section**: Description and detailed grid of all fields
- **Availability Indicators**: Color-coded availability status
- **Cost Information**: Formatted currency display
- **Search Highlighting**: Search terms highlighted in results

## Mobile Responsiveness

### Breakpoints
- **Desktop (≥768px)**: Full grid layout with all details
- **Tablet (576px-767px)**: Adjusted grid with stacked elements
- **Mobile (<576px)**: Single column layout with optimized spacing

### Responsive Features
- Modal sizing adjusts to screen size
- Grid layout collapses to single column on mobile
- Button text hides on small screens (icons only)
- Touch-friendly interface elements

## Performance Features

### Caching Strategy
- **Cache Duration**: 5 minutes
- **Cache Key**: `{search_term}_{site_id}_{limit}`
- **Cache Stats**: Available via API endpoint
- **Cache Management**: Manual clear functionality

### API Optimization
- **Lean Queries**: `lean=1` parameter for faster responses
- **Field Selection**: Only request needed fields
- **Timeout Handling**: 5s connection, 30s read timeout
- **Error Recovery**: Graceful degradation on API failures

## Testing

### Test Script (`test_inventory_search.py`)
Comprehensive test script that validates:
- Authentication status
- Search functionality with multiple test cases
- Performance metrics
- Cache operations
- Error handling

### Test Cases
1. **BOLT** search in LCVKWT site (5 items)
2. **SCREW** search in LCVKWT site (3 items)
3. **VALVE** search in LCVKWT site (2 items)

## Security & Authentication

### Access Control
- Requires valid Maximo authentication
- Uses existing token manager for API calls
- Site-based access control (user's assigned sites only)
- No direct database access - API only

### Data Validation
- Input sanitization for search terms
- SQL injection prevention through OSLC parameters
- XSS prevention in frontend display
- Error message sanitization

## Files Created/Modified

### New Files
1. `backend/services/inventory_search_service.py` - Core search service
2. `frontend/static/js/inventory_search.js` - Frontend JavaScript
3. `frontend/templates/components/inventory_search_modal.html` - Modal UI
4. `test_inventory_search.py` - Test script
5. `INVENTORY_SEARCH_IMPLEMENTATION.md` - This documentation

### Modified Files
1. `app.py` - Added API endpoints and service initialization
2. `frontend/templates/workorder_detail.html` - Added button and modal integration

## Usage Instructions

### For Users
1. Navigate to Work Order Details page
2. Expand any task with status: APPR, ASSIGN, WMATL, or INPRG
3. Click "Search Inventory" button (green outline)
4. Enter search term (item number or description)
5. Select result limit (10, 20, 50, or 100 items)
6. Click "Search" or press Enter
7. Browse results with comprehensive item information

### For Developers
1. Service can be extended for additional search criteria
2. Modal can be customized for different display needs
3. Cache timeout can be adjusted in service configuration
4. Additional fields can be added to search results

## Future Enhancements

### Potential Improvements
- Advanced search filters (cost range, availability status)
- Export functionality for search results
- Integration with material request workflows
- Barcode scanning for mobile devices
- Favorite items functionality
- Search history and suggestions

## Troubleshooting

### Common Issues
1. **No Results Found**: Check site access and item availability
2. **Slow Performance**: Verify network connection and API response times
3. **Authentication Errors**: Ensure valid Maximo login
4. **Modal Not Opening**: Check JavaScript console for errors

### Debug Information
- Search performance metrics displayed in modal footer
- Cache statistics available via API
- Detailed logging in backend service
- Browser console logs for frontend debugging
