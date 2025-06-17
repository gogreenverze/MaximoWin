#!/usr/bin/env python3
"""
API Field Investigation Script

This script investigates the actual fields and methods available in:
- MXAPIINVENTORY 
- MXAPIITEM

Author: Augment Agent
Date: 2025-01-27
"""

import sys
import os
import json

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.auth.token_manager import MaximoTokenManager

def investigate_api_endpoints():
    """Investigate the actual API endpoints and available fields."""
    print("🔍 API FIELD INVESTIGATION")
    print("=" * 50)
    
    # Check if app is running
    try:
        import requests
        response = requests.get('http://127.0.0.1:5009/api/auth-status', timeout=5)
        if response.status_code != 200:
            print("❌ Application not running or not accessible")
            print("💡 Please start the application first: python3 app.py")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to application: {e}")
        print("💡 Please start the application first: python3 app.py")
        return False
    
    print("✅ Application is running")
    
    # Initialize token manager
    DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
    
    try:
        token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)
    except Exception as e:
        print(f"❌ Failed to initialize token manager: {str(e)}")
        return False
    
    # Check if user is logged in by testing an API call
    try:
        test_response = token_manager.session.get(
            f"{token_manager.base_url}/oslc/whoami",
            timeout=(5.0, 10),
            headers={"Accept": "application/json"}
        )
        if test_response.status_code == 200:
            print(f"✅ User logged in successfully")
        else:
            print("❌ User not logged in or session expired")
            print("💡 Please login to the application first")
            return False
    except Exception as e:
        print(f"❌ Cannot verify login status: {e}")
        print("💡 Please login to the application first")
        return False
    
    # Test MXAPIINVENTORY endpoint
    print(f"\n🔍 INVESTIGATING MXAPIINVENTORY")
    print("-" * 40)
    
    base_url = token_manager.base_url
    inventory_url = f"{base_url}/oslc/os/mxapiinventory"
    
    print(f"📍 URL: {inventory_url}")
    
    # Test 1: Get a single record to see available fields
    params = {
        "oslc.select": "*",
        "oslc.where": 'siteid="LCVKWT"',
        "oslc.pageSize": "1",
        "lean": "1"
    }
    
    try:
        response = token_manager.session.get(
            inventory_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📋 Response Keys: {list(data.keys())}")
                
                items = data.get('member', [])
                print(f"📦 Items Found: {len(items)}")
                
                if items:
                    first_item = items[0]
                    print(f"📝 Available Fields in MXAPIINVENTORY:")
                    for field in sorted(first_item.keys()):
                        value = first_item[field]
                        if isinstance(value, (str, int, float, bool)) and str(value).strip():
                            print(f"   ✓ {field}: {str(value)[:50]}...")
                        else:
                            print(f"   ○ {field}: {type(value).__name__}")
                else:
                    print("⚠️  No inventory items found in LCVKWT site")
                    
            except Exception as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"📄 Response Content: {response.text[:200]}...")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"📄 Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
    
    # Test MXAPIITEM endpoint
    print(f"\n🔍 INVESTIGATING MXAPIITEM")
    print("-" * 40)
    
    item_url = f"{base_url}/oslc/os/mxapiitem"
    print(f"📍 URL: {item_url}")
    
    # Test with a known item number from the materials we saw
    params = {
        "oslc.select": "*",
        "oslc.where": 'itemnum="5975-60-V00-0529"',
        "oslc.pageSize": "1",
        "lean": "1"
    }
    
    try:
        response = token_manager.session.get(
            item_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📋 Response Keys: {list(data.keys())}")
                
                items = data.get('member', [])
                print(f"📦 Items Found: {len(items)}")
                
                if items:
                    first_item = items[0]
                    print(f"📝 Available Fields in MXAPIITEM:")
                    for field in sorted(first_item.keys()):
                        value = first_item[field]
                        if isinstance(value, (str, int, float, bool)) and str(value).strip():
                            print(f"   ✓ {field}: {str(value)[:50]}...")
                        else:
                            print(f"   ○ {field}: {type(value).__name__}")
                else:
                    print("⚠️  Item 5975-60-V00-0529 not found in MXAPIITEM")
                    
            except Exception as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"📄 Response Content: {response.text[:200]}...")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"📄 Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
    
    # Test with any item to see general structure
    print(f"\n🔍 INVESTIGATING MXAPIITEM (ANY ITEM)")
    print("-" * 40)
    
    params = {
        "oslc.select": "*",
        "oslc.where": 'status="ACTIVE"',
        "oslc.pageSize": "1",
        "lean": "1"
    }
    
    try:
        response = token_manager.session.get(
            item_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"}
        )
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                items = data.get('member', [])
                print(f"📦 Items Found: {len(items)}")
                
                if items:
                    first_item = items[0]
                    print(f"📝 Sample Item Fields:")
                    for field in sorted(first_item.keys()):
                        value = first_item[field]
                        if isinstance(value, (str, int, float, bool)) and str(value).strip():
                            print(f"   ✓ {field}: {str(value)[:50]}...")
                        else:
                            print(f"   ○ {field}: {type(value).__name__}")
                            
            except Exception as e:
                print(f"❌ JSON Parse Error: {e}")
                
    except Exception as e:
        print(f"❌ Request Error: {e}")
    
    print(f"\n✅ API INVESTIGATION COMPLETED")
    return True

if __name__ == "__main__":
    try:
        success = investigate_api_endpoints()
        if success:
            print("\n🎉 Investigation completed successfully!")
        else:
            print("\n❌ Investigation failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Investigation interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)
