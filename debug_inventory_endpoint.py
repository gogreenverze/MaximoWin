#!/usr/bin/env python3
"""
Debug script for inventory endpoint

This script tests the MXAPIINVENTORY endpoint to see what's actually being returned.

Author: Augment Agent
Date: 2025-01-27
"""

import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.auth.token_manager import MaximoTokenManager
from backend.services.inventory_search_service import InventorySearchService

def debug_inventory_endpoint():
    """Debug the inventory endpoint to see actual responses."""
    print("🔧 DEBUG INVENTORY ENDPOINT")
    print("=" * 40)
    
    # Initialize
    token_manager = MaximoTokenManager('https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')
    
    if not token_manager.is_logged_in():
        print("❌ Not logged in")
        return
    
    print("✅ Authenticated")
    
    # Test direct API call first
    base_url = token_manager.base_url
    api_url = f"{base_url}/oslc/os/mxapiinventory"
    
    print(f"🔗 Testing URL: {api_url}")
    
    # Simple test with minimal parameters
    params = {
        "oslc.select": "itemnum,siteid",
        "oslc.where": 'siteid="LCVKWT"',
        "oslc.pageSize": "1",
        "lean": "1"
    }
    
    print(f"📋 Parameters: {params}")
    
    try:
        response = token_manager.session.get(
            api_url,
            params=params,
            timeout=(5.0, 30),
            headers={"Accept": "application/json"},
            allow_redirects=True
        )
        
        print(f"📊 Status: {response.status_code}")
        print(f"📏 Content Length: {len(response.text)}")
        print(f"📄 Content Type: {response.headers.get('content-type', 'Unknown')}")
        print(f"📝 Response (first 500 chars): {response.text[:500]}")
        
        if response.text.strip():
            try:
                data = response.json()
                print(f"🔑 JSON Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                if isinstance(data, dict):
                    member = data.get('member', data.get('rdfs:member', []))
                    print(f"📦 Items in member: {len(member)}")
            except Exception as e:
                print(f"❌ JSON Parse Error: {e}")
        else:
            print("⚠️  Empty response body")
            
    except Exception as e:
        print(f"❌ Request Error: {e}")

if __name__ == "__main__":
    debug_inventory_endpoint()
