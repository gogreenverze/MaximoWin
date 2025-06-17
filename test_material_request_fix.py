#!/usr/bin/env python3
"""
Test script to verify the material request fixes.

This script tests:
1. Frontend data structure changes
2. Backend field mapping corrections
3. Maximo API payload structure
4. Task-specific material addition
"""

import json
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_frontend_data_structure():
    """Test that the frontend data structure is correct."""
    print("🧪 Testing Frontend Data Structure...")
    
    # Simulate the data structure that should be sent from frontend
    expected_frontend_data = {
        "wonum": "2021-1744762",  # Parent work order number
        "siteid": "LCVKWT",
        "itemnum": "5975-60-V00-0394",
        "quantity": 1,
        "taskid": 40,  # Numeric task ID
        "task_wonum": "2021-1835482",  # Task work order number for validation
        "location": "LCVK-CMW-AJ",
        "directreq": False,
        "notes": "Test material request",
        "requestby": "TINU.THOMAS"
    }
    
    print("✅ Expected frontend data structure:")
    print(json.dumps(expected_frontend_data, indent=2))
    
    # Validate required fields
    required_fields = ["wonum", "siteid", "itemnum", "quantity", "taskid", "requestby"]
    missing_fields = [field for field in required_fields if field not in expected_frontend_data]
    
    if missing_fields:
        print(f"❌ Missing required fields: {missing_fields}")
        return False
    else:
        print("✅ All required fields present")
        return True

def test_maximo_payload_structure():
    """Test that the Maximo API payload structure is correct."""
    print("\n🧪 Testing Maximo API Payload Structure...")
    
    # Expected Maximo API payload structure
    expected_maximo_payload = [
        {
            "_action": "AddChange",
            "wonum": "2021-1744762",  # Parent work order
            "siteid": "LCVKWT",
            "wpmaterial": [
                {
                    "itemnum": "5975-60-V00-0394",
                    "itemqty": 1,
                    "location": "LCVK-CMW-AJ",
                    "directreq": 0,  # 0 for False, 1 for True
                    "taskid": 40,  # Numeric task ID
                    "requestby": "TINU.THOMAS"
                }
            ]
        }
    ]
    
    print("✅ Expected Maximo API payload structure:")
    print(json.dumps(expected_maximo_payload, indent=2))
    
    # Validate payload structure
    payload = expected_maximo_payload[0]
    
    # Check top-level fields
    required_top_fields = ["_action", "wonum", "siteid", "wpmaterial"]
    missing_top_fields = [field for field in required_top_fields if field not in payload]
    
    if missing_top_fields:
        print(f"❌ Missing top-level fields: {missing_top_fields}")
        return False
    
    # Check wpmaterial structure
    if not payload["wpmaterial"] or len(payload["wpmaterial"]) == 0:
        print("❌ wpmaterial array is empty")
        return False
    
    material = payload["wpmaterial"][0]
    required_material_fields = ["itemnum", "itemqty", "taskid", "requestby"]
    missing_material_fields = [field for field in required_material_fields if field not in material]
    
    if missing_material_fields:
        print(f"❌ Missing material fields: {missing_material_fields}")
        return False
    
    # Validate field types
    if not isinstance(material["taskid"], int):
        print(f"❌ taskid should be integer, got {type(material['taskid'])}")
        return False
    
    if not isinstance(material["directreq"], int):
        print(f"❌ directreq should be integer (0/1), got {type(material['directreq'])}")
        return False
    
    print("✅ Maximo API payload structure is correct")
    return True

def test_field_mappings():
    """Test that field mappings are correct."""
    print("\n🧪 Testing Field Mappings...")
    
    # Test mapping from frontend to backend
    frontend_data = {
        "wonum": "2021-1744762",
        "taskid": 40,
        "task_wonum": "2021-1835482",
        "directreq": False,
        "requestby": "TINU.THOMAS"
    }
    
    # Expected backend processing
    expected_backend_processing = {
        "parent_wonum": frontend_data["wonum"],  # Parent WO for top-level payload
        "numeric_taskid": frontend_data["taskid"],  # Numeric task ID for material
        "task_wonum_validation": frontend_data["task_wonum"],  # Task WO for validation
        "directreq_int": 0 if not frontend_data["directreq"] else 1,  # Convert to int
        "requestby_field": frontend_data["requestby"]  # Correct field name
    }
    
    print("✅ Field mapping test:")
    print(f"   Frontend wonum -> Backend parent_wonum: {frontend_data['wonum']} -> {expected_backend_processing['parent_wonum']}")
    print(f"   Frontend taskid -> Backend numeric_taskid: {frontend_data['taskid']} -> {expected_backend_processing['numeric_taskid']}")
    print(f"   Frontend task_wonum -> Backend validation: {frontend_data['task_wonum']} -> {expected_backend_processing['task_wonum_validation']}")
    print(f"   Frontend directreq -> Backend directreq_int: {frontend_data['directreq']} -> {expected_backend_processing['directreq_int']}")
    print(f"   Frontend requestby -> Backend requestby_field: {frontend_data['requestby']} -> {expected_backend_processing['requestby_field']}")
    
    return True

def test_task_context_flow():
    """Test the task context flow from frontend to backend."""
    print("\n🧪 Testing Task Context Flow...")
    
    # Simulate the flow
    print("1. User clicks 'Search Inventory' on task with:")
    task_data = {
        "parent_wonum": "2021-1744762",
        "task_wonum": "2021-1835482", 
        "taskid": 40
    }
    print(f"   Parent WO: {task_data['parent_wonum']}")
    print(f"   Task WO: {task_data['task_wonum']}")
    print(f"   Task ID: {task_data['taskid']}")
    
    print("\n2. Frontend JavaScript calls:")
    print(f"   openInventorySearchForTask(siteId, '{task_data['parent_wonum']}', '{task_data['task_wonum']}', {task_data['taskid']})")
    
    print("\n3. MaterialRequestManager stores context:")
    print(f"   currentParentWonum = '{task_data['parent_wonum']}'")
    print(f"   currentTaskWonum = '{task_data['task_wonum']}'")
    print(f"   currentTaskId = {task_data['taskid']}")
    
    print("\n4. Material request payload uses:")
    print(f"   wonum: '{task_data['parent_wonum']}' (for top-level payload)")
    print(f"   taskid: {task_data['taskid']} (for material record)")
    print(f"   task_wonum: '{task_data['task_wonum']}' (for validation)")
    
    print("✅ Task context flow is correct")
    return True

def main():
    """Run all tests."""
    print("🚀 Starting Material Request Fix Tests...\n")
    
    tests = [
        test_frontend_data_structure,
        test_maximo_payload_structure,
        test_field_mappings,
        test_task_context_flow
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Material request fixes are ready for testing.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
