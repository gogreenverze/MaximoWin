#!/usr/bin/env python3
"""
Test script to verify material refresh functionality.
This script tests the cache clearing mechanism after material addition.
"""

import requests
import json
import time

def test_material_refresh():
    """Test the material refresh functionality."""
    
    base_url = "http://127.0.0.1:5009"
    
    print("🧪 Testing Material Refresh Functionality")
    print("=" * 50)
    
    # Test 1: Check if cache clear endpoint is working
    print("\n1. Testing cache clear endpoint...")
    try:
        response = requests.post(
            f"{base_url}/api/task/planned-materials/cache/clear",
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Cache clear endpoint working correctly")
            else:
                print(f"❌ Cache clear failed: {result.get('error')}")
        else:
            print(f"❌ Cache clear endpoint returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing cache clear: {e}")
    
    # Test 2: Check cache stats endpoint
    print("\n2. Testing cache stats endpoint...")
    try:
        response = requests.get(
            f"{base_url}/api/task/planned-materials/cache/stats",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                stats = result.get('stats', {})
                print(f"✅ Cache stats: {json.dumps(stats, indent=2)}")
            else:
                print(f"❌ Cache stats failed: {result.get('error')}")
        else:
            print(f"❌ Cache stats endpoint returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing cache stats: {e}")
    
    # Test 3: Test materials availability endpoint
    print("\n3. Testing materials availability endpoint...")
    test_wonum = "2021-1744762"  # Use a known work order
    try:
        response = requests.get(
            f"{base_url}/api/workorder/{test_wonum}/materials-availability",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                availability = result.get('availability', {})
                print(f"✅ Materials availability for WO {test_wonum}:")
                print(f"   - Has materials: {availability.get('has_materials')}")
                print(f"   - Total materials: {availability.get('total_materials')}")
                print(f"   - Tasks with materials: {availability.get('tasks_with_materials')}")
                print(f"   - Cache hit: {availability.get('cache_hit')}")
            else:
                print(f"❌ Materials availability failed: {result.get('error')}")
        else:
            print(f"❌ Materials availability endpoint returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing materials availability: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Material refresh functionality test completed")

if __name__ == "__main__":
    test_material_refresh()
