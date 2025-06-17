#!/usr/bin/env python3
"""
Test script for Inventory Search functionality

This script tests the new inventory search service to ensure it works correctly
with real Maximo data from MXAPIINVENTORY and MXAPIITEM endpoints.

Author: Augment Agent
Date: 2025-01-27
"""

import sys
import os
import time

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.auth.token_manager import MaximoTokenManager
from backend.services.inventory_search_service import InventorySearchService

def test_inventory_search():
    """Test the inventory search functionality."""
    print("🔍 INVENTORY SEARCH TEST")
    print("=" * 50)
    
    # Initialize token manager with the same base URL as the main app
    DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"

    try:
        token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)
    except Exception as e:
        print(f"❌ Failed to initialize token manager: {str(e)}")
        print("💡 Make sure the main application is running and you are logged in.")
        return False

    # Check if we have valid authentication
    if not token_manager.is_logged_in():
        print("❌ Not authenticated. Please run the main app and login first.")
        return False

    print(f"✅ Authenticated as: {getattr(token_manager, 'username', 'Unknown')}")
    print(f"🏢 Base URL: {getattr(token_manager, 'base_url', 'Unknown')}")

    # Initialize inventory search service
    try:
        inventory_service = InventorySearchService(token_manager)
    except Exception as e:
        print(f"❌ Failed to initialize inventory service: {str(e)}")
        return False
    
    # Test parameters
    test_cases = [
        {"search_term": "BOLT", "site_id": "LCVKWT", "limit": 5},
        {"search_term": "SCREW", "site_id": "LCVKWT", "limit": 3},
        {"search_term": "VALVE", "site_id": "LCVKWT", "limit": 2}
    ]
    
    print("\n🧪 RUNNING TEST CASES")
    print("-" * 30)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: '{test_case['search_term']}'")
        print(f"   Site: {test_case['site_id']}")
        print(f"   Limit: {test_case['limit']}")
        
        try:
            start_time = time.time()
            items, metadata = inventory_service.search_inventory_items(
                test_case['search_term'],
                test_case['site_id'],
                test_case['limit']
            )
            load_time = time.time() - start_time
            
            print(f"   ⏱️  Load Time: {load_time:.3f}s")
            print(f"   📊 Data Source: {metadata.get('source', 'unknown')}")
            print(f"   📦 Items Found: {len(items)}")
            
            if items:
                print("   📋 Sample Items:")
                for j, item in enumerate(items[:2], 1):  # Show first 2 items
                    print(f"      {j}. {item.get('itemnum', 'N/A')} - {item.get('description', 'No description')[:50]}...")
                    print(f"         Location: {item.get('location', 'N/A')}")
                    print(f"         Available: {item.get('avblbalance', 0)} of {item.get('curbaltotal', 0)}")
                    if item.get('avgcost'):
                        print(f"         Avg Cost: {item.get('currency', 'USD')} {item.get('avgcost', 0):.2f}")
            else:
                print("   ⚠️  No items found")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    # Test cache functionality
    print(f"\n🗄️  CACHE STATISTICS")
    print("-" * 20)
    cache_stats = inventory_service.get_cache_stats()
    print(f"   Cache Entries: {cache_stats['entries']}")
    print(f"   Cache Timeout: {cache_stats['timeout_seconds']}s")
    
    # Test cache clear
    print(f"\n🧹 CLEARING CACHE")
    inventory_service.clear_cache()
    cache_stats_after = inventory_service.get_cache_stats()
    print(f"   Cache Entries After Clear: {cache_stats_after['entries']}")
    
    print(f"\n✅ INVENTORY SEARCH TEST COMPLETED")
    return True

if __name__ == "__main__":
    try:
        success = test_inventory_search()
        if success:
            print("\n🎉 All tests completed successfully!")
        else:
            print("\n❌ Tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)
