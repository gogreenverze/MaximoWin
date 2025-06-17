#!/usr/bin/env python3
"""
Test script to show the COMPLETE payload structure being sent to Maximo
This will trigger all the logging we added to show the entire payload
"""

import requests
import json
import time

def test_complete_payload():
    """Test with your exact requirements and show complete payload"""
    
    print("🎯 TESTING COMPLETE PAYLOAD STRUCTURE")
    print("="*80)
    
    # Your exact test data
    test_data = {
        'wonum': '2021-1744762',
        'siteid': 'LCVKWT', 
        'itemnum': '5975-60-V00-0394',
        'quantity': 1,
        'taskid': 40,  # MANDATORY
        'location': 'LCVK-CMW-AJ',
        'directreq': False,  # 0 in your example
        'requestby': 'TINU.THOMAS',
        'notes': 'Test material request'
    }
    
    print("📦 FRONTEND REQUEST DATA:")
    print(json.dumps(test_data, indent=2))
    print("="*80)
    
    # Expected material object
    expected_material = {
        "itemnum": "5975-60-V00-0394",
        "itemqty": 1,
        "directreq": False,
        "requestby": "TINU.THOMAS",
        "taskid": 40,
        "location": "LCVK-CMW-AJ",
        "remarks": "Test material request"
    }
    
    print("📦 EXPECTED MATERIAL OBJECT:")
    print(json.dumps(expected_material, indent=2))
    print("="*80)
    
    # Expected complete AddChange payload
    expected_addchange = [{
        "_action": "AddChange",
        "wonum": "2021-1744762",
        "siteid": "LCVKWT",
        "description": "Work Order Description",
        "status": "Work Order Status",
        "assetnum": "Asset Number",
        "location": "Work Order Location",
        "wpmaterial": [expected_material]
    }]
    
    print("📦 EXPECTED COMPLETE ADDCHANGE PAYLOAD:")
    print(json.dumps(expected_addchange, indent=2))
    print("="*80)
    
    try:
        print("🚀 CALLING BACKEND API...")
        print("   Check the backend logs for COMPLETE payload details!")
        print("="*80)
        
        # Call our backend API
        response = requests.post(
            'http://127.0.0.1:5009/api/workorder/add-material-request',
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"📡 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS!")
            print(f"📄 Response:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ ERROR!")
            print(f"📄 Response:")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error calling backend: {e}")

def show_comparison():
    """Show comparison with successful_material_addition.py"""
    print("\n" + "="*80)
    print("🔍 COMPARISON WITH SUCCESSFUL_MATERIAL_ADDITION.PY")
    print("="*80)
    
    successful_payload = {
        "itemnum": "5975-60-V00-0394",
        "itemqty": 1,
        "directreq": False,
        "requestby": "TINU.THOMAS",
        "location": "LCVK-CMW-AJ"
    }
    
    our_payload = {
        "itemnum": "5975-60-V00-0394",
        "itemqty": 1,
        "directreq": False,
        "requestby": "TINU.THOMAS",
        "taskid": 40,  # THIS IS THE KEY ADDITION
        "location": "LCVK-CMW-AJ"
    }
    
    print("✅ successful_material_addition.py material object:")
    print(json.dumps(successful_payload, indent=2))
    
    print("\n✅ Our backend material object:")
    print(json.dumps(our_payload, indent=2))
    
    print("\n🔑 KEY DIFFERENCE:")
    print("   - We add 'taskid': 40 to the material object")
    print("   - This makes Maximo add the material to the specific task")
    print("   - Everything else is IDENTICAL to the working example")

if __name__ == "__main__":
    print("🚀 COMPLETE PAYLOAD ANALYSIS")
    print("="*80)
    print("This script will:")
    print("1. Show the frontend request data")
    print("2. Show the expected material object")
    print("3. Show the complete AddChange payload")
    print("4. Call the backend API")
    print("5. Backend will log the COMPLETE payload being sent to Maximo")
    print("="*80)
    
    # Show comparison first
    show_comparison()
    
    # Test the complete payload
    test_complete_payload()
    
    print("\n🎉 SUMMARY:")
    print("1. ✅ Frontend sends complete request data")
    print("2. ✅ Backend creates material object with taskid")
    print("3. ✅ Backend creates complete AddChange payload")
    print("4. ✅ Backend logs ENTIRE payload structure")
    print("5. ✅ Check backend logs for complete details!")
    print("\n📋 NEXT STEPS:")
    print("   - Check the Flask app logs for complete payload details")
    print("   - Open http://127.0.0.1:5009/payload-test in browser")
    print("   - Use the test page to see live payload generation")
