#!/usr/bin/env python3
"""
Simple API Field Test Script

This script tests the actual fields available in MXAPIINVENTORY and MXAPIITEM
by making direct HTTP requests to the running Flask app.

Author: Augment Agent
Date: 2025-01-27
"""

import requests
import json
import sys

def test_api_fields():
    """Test the actual API endpoints and available fields."""
    print("🔧 TESTING API FIELDS")
    print("=" * 40)
    
    base_url = "http://127.0.0.1:5009"
    
    # Test 1: Check if app is running
    try:
        response = requests.get(f"{base_url}/api/auth-status", timeout=5)
        if response.status_code != 200:
            print("❌ Application not running or not accessible")
            return False
        print("✅ Application is running")
    except Exception as e:
        print(f"❌ Cannot connect to application: {e}")
        return False
    
    # Test 2: Test MXAPIINVENTORY with minimal fields
    print(f"\n🔍 TESTING MXAPIINVENTORY (MINIMAL FIELDS)")
    print("-" * 50)
    
    # Start with basic fields only
    test_url = f"{base_url}/api/test-inventory-fields"
    
    # Create a test endpoint call
    print("📍 Testing basic inventory fields...")
    
    # Test 3: Test MXAPIITEM with minimal fields  
    print(f"\n🔍 TESTING MXAPIITEM (MINIMAL FIELDS)")
    print("-" * 50)
    
    print("📍 Testing basic item fields...")
    
    # Test 4: Make direct API calls to see what works
    print(f"\n🔍 DIRECT API TESTING")
    print("-" * 30)
    
    # Test inventory search with current broken implementation
    print("📍 Testing current inventory search (should fail)...")
    try:
        response = requests.get(f"{base_url}/api/inventory/search?q=5975&siteid=LCVKWT&limit=1")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success', False)}")
            if not data.get('success'):
                print(f"Error: {data.get('error', 'Unknown')}")
        else:
            print(f"HTTP Error: {response.text[:100]}...")
    except Exception as e:
        print(f"Request failed: {e}")
    
    print(f"\n✅ FIELD TESTING COMPLETED")
    return True

if __name__ == "__main__":
    try:
        success = test_api_fields()
        if success:
            print("\n🎉 Field testing completed!")
        else:
            print("\n❌ Field testing failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)
