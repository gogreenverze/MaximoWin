# Material Request Fixes Summary

## Overview
This document summarizes the fixes implemented to resolve material request issues in the application that sends data to Maximo. The fixes address incorrect data capture in the frontend and wrong field mappings in the backend when adding materials to tasks.

## Issues Fixed

### 1. Frontend Task Context Issue
**Problem**: The frontend was not properly capturing and passing task context data for material requests.

**Solution**: 
- Updated `openInventorySearchForTask()` function to accept and pass both parent work order number and task work order number
- Modified `MaterialRequestManager` class to store complete task context including:
  - `currentParentWonum`: Parent work order number (e.g., "2021-1744762")
  - `currentTaskWonum`: Task work order number (e.g., "2021-1835482") 
  - `currentTaskId`: Numeric task ID (e.g., 40)

### 2. Field Mapping Corrections
**Problem**: Incorrect field mappings between frontend form data and Maximo API payload.

**Solution**:
- **taskid**: Now correctly uses numeric task ID (e.g., 40) instead of task wonum
- **wonum**: Uses parent work order number for top-level payload structure
- **requestby**: Correctly mapped (not `requestedby`)
- **directreq**: Properly converted from boolean to integer (0/1)

### 3. Backend Service Updates
**Problem**: Backend validation logic was causing mismatches and incorrect payload construction.

**Solution**:
- Updated `MaterialRequestService.add_material_request()` method signature to accept `task_wonum` parameter
- Improved validation logic to handle task context properly
- Enhanced logging for better debugging

### 4. API Endpoint Enhancements
**Problem**: API endpoint wasn't processing all required task context data.

**Solution**:
- Updated `/api/workorder/add-material-request` endpoint to handle `task_wonum` parameter
- Enhanced request data validation and logging
- Improved error handling for task-specific requests

## Files Modified

### Frontend Changes
1. **`frontend/templates/workorder_detail.html`**
   - Line 973: Updated `openInventorySearchForTask()` call to pass task wonum
   - Lines 1098-1109: Enhanced function to handle complete task context

2. **`frontend/static/js/inventory_search.js`**
   - Lines 377-396: Updated `MaterialRequestManager` constructor and `setTaskContext()` method
   - Lines 552-570: Enhanced material request submission with correct field mappings

### Backend Changes
3. **`backend/services/material_request_service.py`**
   - Lines 35-38: Updated method signature to include `task_wonum` parameter
   - Lines 39-52: Updated docstring with correct parameter descriptions
   - Lines 65-78: Improved validation logic for task context

4. **`app.py`**
   - Lines 4106-4116: Enhanced taskid and task_wonum processing
   - Lines 4132-4138: Improved logging for debugging
   - Lines 4140-4152: Updated service call to include task_wonum parameter

## Data Flow

### 1. Frontend Task Context Setting
```javascript
// User clicks "Search Inventory" on task
openInventorySearchForTask(siteId, parentWonum, taskWonum, taskId)
// Sets: currentParentWonum, currentTaskWonum, currentTaskId
```

### 2. Material Request Submission
```javascript
const requestData = {
    wonum: this.currentParentWonum,      // Parent WO for top-level payload
    siteid: this.currentSiteId,
    itemnum: this.selectedItem.itemnum,
    quantity: quantity,
    taskid: this.currentTaskId,          // Numeric task ID for Maximo
    task_wonum: this.currentTaskWonum,   // Task WO for validation
    location: location,
    directreq: directRequest,
    notes: notes,
    requestby: requestBy
};
```

### 3. Maximo API Payload Structure
```json
[
  {
    "_action": "AddChange",
    "wonum": "2021-1744762",           // Parent work order
    "siteid": "LCVKWT",
    "wpmaterial": [
      {
        "itemnum": "5975-60-V00-0394",
        "itemqty": 1,
        "location": "LCVK-CMW-AJ",
        "directreq": 0,                // 0 for false, 1 for true
        "taskid": 40,                  // Numeric task ID
        "requestby": "TINU.THOMAS"
      }
    ]
  }
]
```

## Testing

### Test Script
Created `test_material_request_fix.py` to verify:
- ✅ Frontend data structure correctness
- ✅ Maximo API payload structure compliance
- ✅ Field mapping accuracy
- ✅ Task context flow integrity

### Test Results
- **4/4 tests passed** (100% success rate)
- All required fields properly mapped
- Correct data types and structures validated
- Task context flow verified

## Key Improvements

1. **Correct Task ID Usage**: Now uses numeric task ID (e.g., 40) in Maximo API payload as required
2. **Proper Parent WO Handling**: Uses parent work order number for top-level payload structure
3. **Enhanced Validation**: Added task_wonum for optional backend validation
4. **Better Error Handling**: Improved logging and error messages for debugging
5. **Field Name Accuracy**: Corrected `requestby` field name (not `requestedby`)

## Next Steps

1. **Deploy Changes**: Deploy the updated code to testing environment
2. **Integration Testing**: Test complete flow from frontend form to Maximo API
3. **User Acceptance Testing**: Verify materials are correctly added to specific tasks
4. **Monitor Logs**: Check application logs for successful material additions
5. **Validate in Maximo**: Confirm materials appear in correct tasks in Maximo system

## Validation Checklist

- [ ] Frontend captures correct task context when "Search Inventory" is clicked
- [ ] Material request form pre-populates with selected item data
- [ ] Request payload contains correct field mappings
- [ ] Backend service processes task context properly
- [ ] Maximo API receives correctly formatted payload
- [ ] Materials are added to specific tasks (not parent work order)
- [ ] Success/error messages display correctly to user
- [ ] Application logs show detailed debugging information

## Memory Updates
The fixes align with existing memories about:
- Using `requestby` field (not `requestedby`)
- Adding materials to specific taskid rather than parent work order
- Using numeric task ID in Maximo API payload structure
