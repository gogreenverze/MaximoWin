# Two-Stage Search Implementation - MXAPIITEM + MXAPIINVENTORY

## Overview
This document describes the implementation of a two-stage search strategy for material request functionality, using MXAPIITEM for item discovery and MXAPIINVENTORY for inventory data enhancement.

## Implementation Strategy

### Stage 1: MXAPIITEM Search (Item Discovery)
**Endpoint**: `/api/os/mxapiitem`
**Purpose**: Primary search to find items by partial item number or description matching

**Search Filters**:
1. **Exact item number match**: `itemnum="{search_term}" and status="ACTIVE"`
2. **Partial item number match**: `itemnum~"{search_term}" and status="ACTIVE"`
3. **Partial description match**: `description~"{search_term}" and status="ACTIVE"`

**Fields Retrieved**:
```
itemnum,description,unitcost,issueunit,status,itemtype,rotating,abc,vendor,manufacturer,modelnum
```

**Benefits**:
- Comprehensive item discovery across all items in Maximo
- Supports both exact and partial matching
- Finds items regardless of inventory status
- Fast search with lean response

### Stage 2: MXAPIINVENTORY Enhancement (Inventory Data)
**Endpoint**: `/api/os/mxapiinventory`
**Purpose**: Enhance each found item with comprehensive inventory data

**Search Filter**: `siteid="{site_id}" and itemnum="{item_num}"`

**Fields Retrieved**:
```
itemnum,description,unitcost,issueunit,status,siteid,location,binnum,curbal,storeloc,orderunit,
currencycode,currency,basecurrency,avgcost,stdcost,lastcost,itemsetid,itemtype,rotating,
lottype,conditionenabled,physcnt,physcntdate,abc,vendor,manufacturer,modelnum,serialnum,
lotnum,conditioncode,reservedqty,hardreservedqty,softreservedqty,invbalances{*},invcost{*}
```

**Benefits**:
- Complete inventory information including related tables
- Site-specific inventory data
- Balance and cost information
- Storeroom and location details

## Data Flow

### 1. Item Discovery Process
```python
def _search_item_master_primary(self, search_term: str, limit: int):
    # Search MXAPIITEM with multiple filter strategies
    # Return list of items with basic information
    # Mark items as has_inventory_data = False
```

### 2. Inventory Enhancement Process
```python
def _enhance_items_with_inventory_data(self, items: List, site_id: str):
    # For each item from Stage 1:
    #   Query MXAPIINVENTORY for inventory data
    #   If found: merge item master + inventory data
    #   If not found: keep item master data only
    #   Mark has_inventory_data appropriately
```

### 3. Data Merging Process
```python
def _merge_item_with_inventory(self, item_master_data, inventory_data):
    # Start with item master data as base
    # Overlay inventory-specific fields
    # Prioritize inventory data for costs and balances
    # Preserve item master descriptions
```

## Conditional Storeroom Handling

### Items WITH Inventory Data (`has_inventory_data = true`)
**Frontend Behavior**:
- ✅ Storeroom dropdown **ENABLED**
- ✅ Direct request checkbox **ENABLED** and unchecked
- ✅ Pre-select storeroom if available in inventory
- ✅ Show "Available in inventory" indicator
- ✅ Display comprehensive inventory information

**User Experience**:
- Users can select from available storerooms
- Full inventory visibility (balances, costs, bins)
- Normal material request workflow

### Items WITHOUT Inventory Data (`has_inventory_data = false`)
**Frontend Behavior**:
- ❌ Storeroom dropdown **DISABLED** (grayed out)
- ❌ Direct request checkbox **CHECKED** and disabled
- ⚠️ Show "Direct request required" indicator
- ⚠️ Display warning message about no inventory data

**User Experience**:
- Clear indication that item is not in inventory
- Automatic direct request selection
- Users understand why storeroom selection is unavailable

## Implementation Details

### Backend Changes (`task_material_request_service.py`)

#### 1. Main Search Method
```python
def search_inventory_items(self, search_term: str, site_id: str, limit: int = 20):
    # Stage 1: Search MXAPIITEM for item discovery
    items_from_item_master = self._search_item_master_primary(search_term, limit)
    
    # Stage 2: Enhance with MXAPIINVENTORY data
    enhanced_items = self._enhance_items_with_inventory_data(items_from_item_master, site_id)
    
    return enhanced_items, metadata
```

#### 2. Item Master Search
```python
def _search_item_master_primary(self, search_term: str, limit: int):
    # Multiple search strategies for comprehensive item discovery
    # Clean and normalize item master data
    # Mark items as item_master_only
```

#### 3. Inventory Enhancement
```python
def _enhance_items_with_inventory_data(self, items: List, site_id: str):
    # For each item, query MXAPIINVENTORY
    # Merge data if inventory found
    # Preserve item master data if no inventory
```

#### 4. Data Cleaning Methods
```python
def _clean_item_data(self, item_data):
    # Clean MXAPIITEM data
    # Handle field variations
    # Mark as has_inventory_data = False

def _merge_item_with_inventory(self, item_master_data, inventory_data):
    # Merge item master + inventory data
    # Prioritize appropriate fields
    # Mark as has_inventory_data = True
```

### Frontend Changes (`workorder_detail.html`)

#### 1. Item Selection Logic
```javascript
function selectInventoryItem(item) {
    const hasInventoryData = item.has_inventory_data === true;
    
    if (hasInventoryData) {
        // Enable storeroom selection
        storeLocationSelect.disabled = false;
        directRequestCheckbox.checked = false;
        // Show success indicator
    } else {
        // Disable storeroom, auto-check direct request
        storeLocationSelect.disabled = true;
        directRequestCheckbox.checked = true;
        // Show warning indicator
    }
}
```

#### 2. Visual Indicators
```javascript
// Inventory status badges
if (item.has_inventory_data === true) {
    inventoryStatusInfo = `<span class="badge bg-success">In Inventory</span>`;
} else {
    inventoryStatusInfo = `<span class="badge bg-warning">Direct Request Only</span>`;
}
```

#### 3. Dynamic Labels
```javascript
// Update storeroom label based on inventory status
if (hasInventoryData) {
    label.innerHTML = 'Storeroom <span class="text-success">Available in inventory</span>';
} else {
    label.innerHTML = 'Storeroom <span class="text-warning">Not in inventory - Direct request required</span>';
}
```

## Expected Behavior

### Search Scenarios

#### 1. Exact Item Number Search
- **Input**: `5975-60-V00-0529`
- **Stage 1**: Find item in MXAPIITEM
- **Stage 2**: Enhance with inventory data if available
- **Result**: Item with full information and appropriate storeroom handling

#### 2. Partial Description Search
- **Input**: `valve`
- **Stage 1**: Find all items with "valve" in description
- **Stage 2**: Enhance each with inventory data
- **Result**: Multiple items, some with inventory, some without

#### 3. Mixed Results
- **Items in inventory**: Show with green "In Inventory" badge, enabled storeroom
- **Items not in inventory**: Show with yellow "Direct Request Only" badge, disabled storeroom

### User Experience Flow

1. **User searches** for item by number or description
2. **System displays results** with clear inventory status indicators
3. **User selects item**:
   - If in inventory: Can choose storeroom, see balances/costs
   - If not in inventory: Auto-direct request, clear messaging
4. **User submits request** with appropriate routing

## Benefits

### Technical Benefits
- **Comprehensive item discovery**: Finds all items regardless of inventory status
- **Accurate inventory data**: Real-time inventory information where available
- **Graceful degradation**: Items without inventory still selectable
- **Performance optimization**: Efficient two-stage approach

### User Experience Benefits
- **Clear inventory status**: Users understand item availability immediately
- **Contextual interface**: Storeroom selection only when relevant
- **Informed decisions**: Complete information for inventory items
- **Simplified workflow**: Automatic direct request for non-inventory items

### Business Benefits
- **Complete item catalog access**: No items hidden due to inventory status
- **Accurate material requests**: Proper routing based on inventory availability
- **Reduced errors**: Clear indication of request type required
- **Improved efficiency**: Streamlined workflow for different item types

## Testing Requirements

### Test Cases
1. **Exact item number search** (in inventory)
2. **Exact item number search** (not in inventory)
3. **Partial description search** (mixed results)
4. **Storeroom dropdown behavior** (enabled/disabled)
5. **Direct request auto-selection** (for non-inventory items)
6. **Visual indicators** (badges and labels)

### Validation Points
- ✅ Stage 1 finds items from MXAPIITEM
- ✅ Stage 2 enhances with inventory data where available
- ✅ Items without inventory remain selectable
- ✅ Storeroom dropdown conditional behavior works
- ✅ Direct request auto-selection functions
- ✅ Visual indicators display correctly
- ✅ No mock or hardcoded data used

## Files Modified

### Backend
- `backend/services/task_material_request_service.py`
  - Replaced single-stage with two-stage search
  - Added `_search_item_master_primary()`
  - Added `_enhance_items_with_inventory_data()`
  - Added `_merge_item_with_inventory()`
  - Added `_clean_item_data()`

### Frontend
- `frontend/templates/workorder_detail.html`
  - Enhanced `selectInventoryItem()` with conditional logic
  - Added inventory status indicators
  - Implemented dynamic storeroom dropdown behavior
  - Added visual feedback for inventory status

The two-stage search implementation provides comprehensive item discovery with intelligent inventory-based storeroom handling, ensuring users can find and request any item while understanding the appropriate request method.
