# Comprehensive Inventory API Implementation - MXAPIINVENTORY with Related Tables

## Overview
This document describes the implementation of comprehensive inventory data retrieval using the correct Maximo API endpoints with proper handling of related tables `invbalances` and `invcost`.

## API Endpoint Changes

### Primary Endpoint: MXAPIINVENTORY
**Endpoint**: `/api/os/mxapiinventory` (corrected from `/oslc/os/mxapiinventory`)

**Field Selection with Related Tables**:
```
oslc.select=itemnum,description,unitcost,issueunit,status,siteid,location,binnum,curbal,storeloc,orderunit,currencycode,currency,basecurrency,avgcost,stdcost,lastcost,itemsetid,itemtype,rotating,lottype,conditionenabled,physcnt,physcntdate,abc,vendor,manufacturer,modelnum,serialnum,lotnum,conditioncode,reservedqty,hardreservedqty,softreservedqty,invbalances{*},invcost{*}
```

**Key Changes**:
- Added `invbalances{*}` to retrieve all balance-related data
- Added `invcost{*}` to retrieve all cost-related data
- Included comprehensive inventory fields for complete item information

### Fallback Endpoint: MXAPIITEM
**Endpoint**: `/api/os/mxapiitem`
**Purpose**: Description enhancement and fallback when inventory search yields no results

## Related Table Processing

### INVBALANCES Table Processing
**Purpose**: Comprehensive balance information per location/bin

**Fields Extracted**:
- `location` - Storage location
- `binnum` - Bin number within location
- `curbal` - Current balance quantity
- `physcnt` - Physical count quantity
- `physcntdate` - Physical count date
- `reservedqty` - Reserved quantity
- `hardreservedqty` - Hard reserved quantity
- `softreservedqty` - Soft reserved quantity
- `stagingbin` - Staging bin information
- `conditioncode` - Condition code
- `lotnum` - Lot number
- `available_qty` - Calculated available quantity (curbal - reservedqty)

**Processing Logic**:
```python
def _process_invbalances_table(self, invbalances_data):
    processed_balances = []
    for balance_record in invbalances_data:
        cleaned_balance = {
            'location': balance_record.get('location', ''),
            'binnum': balance_record.get('binnum', ''),
            'curbal': balance_record.get('curbal', 0),
            'available_qty': balance_record.get('curbal', 0) - balance_record.get('reservedqty', 0),
            # ... other fields
        }
        processed_balances.append(cleaned_balance)
    return processed_balances
```

### INVCOST Table Processing
**Purpose**: Comprehensive cost information with different cost types

**Fields Extracted**:
- `costtype` - Type of cost (STANDARD, AVERAGE, LAST, etc.)
- `unitcost` - Unit cost value
- `currencycode` - Currency code for the cost
- `exchangerate` - Exchange rate
- `exchangedate` - Exchange rate date
- `standardcost` - Standard cost
- `averagecost` - Average cost
- `lastcost` - Last cost
- `vendor` - Vendor information
- `contractnum` - Contract number
- `contractlinenum` - Contract line number
- `linecost` - Line cost

**Processing Logic**:
```python
def _process_invcost_table(self, invcost_data):
    processed_costs = []
    for cost_record in invcost_data:
        cleaned_cost = {
            'costtype': cost_record.get('costtype', ''),
            'unitcost': cost_record.get('unitcost', 0),
            'currencycode': cost_record.get('currencycode', ''),
            # ... other fields
        }
        processed_costs.append(cleaned_cost)
    return processed_costs
```

## Enhanced Data Display

### Balance Information Display
**Frontend Implementation**:
- Aggregates balance data from multiple bins/locations
- Shows total balance, available quantity, and reserved quantity
- Displays detailed bin-level breakdown
- Calculates available quantity (total - reserved)

**Example Display**:
```
Balance: 150.00 (Available: 120.00) [Reserved: 30.00]
Detailed: Bin A01: 75.00, Bin B02: 75.00
```

### Cost Information Display
**Frontend Implementation**:
- Prioritizes STANDARD cost type when available
- Falls back to first available cost if no STANDARD cost
- Shows detailed cost breakdown by cost type
- Proper currency formatting based on cost record currency

**Example Display**:
```
Cost: $25.50 (STANDARD)
Detailed: STANDARD: USD 25.50, AVERAGE: USD 24.80, LAST: USD 26.00
```

### Additional Inventory Information
**New Fields Displayed**:
- ABC classification
- Vendor information
- Manufacturer details
- Model number
- Item type and rotation status
- Physical count information
- Condition codes

## Search Enhancement

### Multi-Strategy Search
1. **Primary Search**: Site-specific inventory search
2. **Description Enhancement**: Enhance results with mxapiitem descriptions
3. **Fallback Search**: mxapiitem search when inventory yields no results

### Search Filters
```python
# Site-specific searches
f'siteid="{site_id}" and itemnum="{search_term}"'
f'siteid="{site_id}" and itemnum~"{search_term}"'
f'siteid="{site_id}" and description~"{search_term}"'

# Fallback searches
f'itemnum="{search_term}"'
f'description~"{search_term}"'
```

## Implementation Benefits

### Comprehensive Data Access
- **Complete inventory picture**: Balance, cost, and location data
- **Multi-location support**: Handles items across multiple bins/storerooms
- **Cost transparency**: Multiple cost types with currency information
- **Real-time accuracy**: Direct from Maximo with no cached/stale data

### Enhanced User Experience
- **Informed decisions**: Users see complete inventory status
- **Location awareness**: Clear bin and storeroom information
- **Cost visibility**: Transparent pricing with currency handling
- **Availability clarity**: Available vs. reserved quantity distinction

### Technical Robustness
- **Proper API usage**: Correct endpoint paths and field selection
- **Related table handling**: Proper OSLC relationship processing
- **Error resilience**: Fallback mechanisms for data retrieval
- **Performance optimization**: Efficient field selection and processing

## Testing Requirements

### Test Cases
1. **Related Table Data**: Verify invbalances and invcost data retrieval
2. **Multi-Bin Items**: Test items with multiple bin locations
3. **Multiple Cost Types**: Verify different cost type handling
4. **Currency Handling**: Test various currency codes
5. **Reserved Quantities**: Verify available quantity calculations
6. **Fallback Mechanism**: Test mxapiitem fallback functionality

### Validation Points
- ✅ invbalances data properly processed and displayed
- ✅ invcost data shows multiple cost types with currencies
- ✅ Available quantity calculated correctly (total - reserved)
- ✅ Bin-level detail information displayed
- ✅ Vendor, manufacturer, and ABC data shown
- ✅ Proper currency formatting from cost records
- ✅ Fallback to mxapiitem when inventory search fails

## Files Modified

### Backend Changes
- `backend/services/task_material_request_service.py`
  - Updated API endpoint path
  - Enhanced field selection with related tables
  - Added `_process_invbalances_table()` method
  - Added `_process_invcost_table()` method
  - Enhanced `_clean_inventory_item_data()` method

### Frontend Changes
- `frontend/templates/workorder_detail.html`
  - Enhanced balance display with aggregation
  - Improved cost display with cost type prioritization
  - Added detailed breakdown information
  - Enhanced item information display

## Next Steps
1. Test with real Maximo data to verify related table retrieval
2. Validate balance calculations and cost type handling
3. Confirm proper display of comprehensive inventory information
4. Test fallback mechanisms with various search scenarios
