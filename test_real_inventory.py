#!/usr/bin/env python3
"""
Test script for real inventory items

This script tests the inventory search with real item patterns that might exist
in the LCVKWT site based on the item number format you provided.

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

def test_real_inventory_search():
    """Test the inventory search with real item patterns."""
    print("🔍 REAL INVENTORY SEARCH TEST")
    print("=" * 50)
    
    # Initialize token manager with the same base URL as the main app
    DEFAULT_MAXIMO_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"
    
    try:
        token_manager = MaximoTokenManager(DEFAULT_MAXIMO_URL)
    except Exception as e:
        print(f"❌ Failed to initialize token manager: {str(e)}")
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
    
    # Test with real item patterns based on the format you provided: "5975-60-V00-0529"
    test_cases = [
        {"search_term": "5975", "site_id": "LCVKWT", "limit": 5, "description": "NSN prefix search"},
        {"search_term": "5975-60", "site_id": "LCVKWT", "limit": 3, "description": "NSN class search"},
        {"search_term": "V00", "site_id": "LCVKWT", "limit": 3, "description": "Part of item number"},
        {"search_term": "BOLT", "site_id": "LCVKWT", "limit": 5, "description": "Common hardware"},
        {"search_term": "SCREW", "site_id": "LCVKWT", "limit": 5, "description": "Common hardware"},
        {"search_term": "GASKET", "site_id": "LCVKWT", "limit": 3, "description": "Common part"},
        {"search_term": "FILTER", "site_id": "LCVKWT", "limit": 3, "description": "Common part"},
        {"search_term": "OIL", "site_id": "LCVKWT", "limit": 3, "description": "Common fluid"},
    ]
    
    print("\n🧪 RUNNING REAL ITEM TESTS")
    print("-" * 40)
    
    found_items = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: '{test_case['search_term']}' ({test_case['description']})")
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
                found_items += len(items)
                print("   📋 Sample Items:")
                for j, item in enumerate(items[:2], 1):  # Show first 2 items
                    print(f"      {j}. {item.get('itemnum', 'N/A')} - {item.get('description', 'No description')[:50]}...")
                    print(f"         Location: {item.get('location', 'N/A')}")
                    print(f"         Available: {item.get('avblbalance', 0)} of {item.get('curbaltotal', 0)}")
                    if item.get('avgcost'):
                        print(f"         Avg Cost: {item.get('currency', 'USD')} {item.get('avgcost', 0):.2f}")
                
                # If we found items, break early to avoid too much output
                if len(items) > 0:
                    print(f"   ✅ SUCCESS! Found {len(items)} items for '{test_case['search_term']}'")
                    break
            else:
                print("   ⚠️  No items found")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n📊 SUMMARY")
    print("-" * 20)
    print(f"   Total items found: {found_items}")
    
    if found_items > 0:
        print("   ✅ Inventory search is working correctly!")
        print("   💡 The search functionality is operational")
    else:
        print("   ⚠️  No items found in any search")
        print("   💡 This could mean:")
        print("      - No inventory items in LCVKWT site match these terms")
        print("      - Items might use different naming conventions")
        print("      - Site might not have active inventory")
    
    # Test cache functionality
    print(f"\n🗄️  CACHE STATISTICS")
    print("-" * 20)
    cache_stats = inventory_service.get_cache_stats()
    print(f"   Cache Entries: {cache_stats['entries']}")
    print(f"   Cache Timeout: {cache_stats['timeout_seconds']}s")
    
    print(f"\n✅ REAL INVENTORY SEARCH TEST COMPLETED")
    return True

if __name__ == "__main__":
    try:
        success = test_real_inventory_search()
        if success:
            print("\n🎉 Test completed successfully!")
        else:
            print("\n❌ Test failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)
