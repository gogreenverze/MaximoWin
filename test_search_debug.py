#!/usr/bin/env python3
"""
Test script to debug the material search functionality.
This script will test the debug endpoint to see what's happening with the search.
"""

import requests
import json
import sys

def test_debug_search(search_term="pump"):
    """Test the debug search endpoint."""

    # Test the debug endpoint
    debug_url = "http://127.0.0.1:5009/api/inventory/debug-search"

    print(f"🔍 Testing debug search for term: '{search_term}'")
    print(f"🔍 Debug URL: {debug_url}")

    try:
        # Make request to debug endpoint
        response = requests.get(debug_url, params={'q': search_term, 'limit': 5})

        print(f"🔍 Response status: {response.status_code}")
        print(f"🔍 Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"🔍 Response success: {data.get('success', 'Unknown')}")
                print(f"🔍 Items found: {len(data.get('items', []))}")
                print(f"🔍 Search term: {data.get('search_term', 'Unknown')}")
                print(f"🔍 Site ID: {data.get('site_id', 'Unknown')}")

                # Print full response for debugging
                print(f"\n🔍 FULL RESPONSE:")
                print(json.dumps(data, indent=2))

                # Print debug info
                debug_info = data.get('debug_info', {})
                if debug_info:
                    print("\n🔍 DEBUG INFO:")
                    print(json.dumps(debug_info, indent=2))

                # Print items found
                items = data.get('items', [])
                if items:
                    print(f"\n🔍 ITEMS FOUND ({len(items)}):")
                    for i, item in enumerate(items):
                        print(f"  {i+1}. {item.get('itemnum', 'No itemnum')} - {item.get('description', 'No description')}")
                else:
                    print("\n🔍 NO ITEMS FOUND")

                # Print metadata
                metadata = data.get('metadata', {})
                if metadata:
                    print(f"\n🔍 METADATA:")
                    print(json.dumps(metadata, indent=2))

            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"❌ Raw response: {response.text[:500]}")
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")

def test_regular_search(search_term="pump"):
    """Test the regular search endpoint."""

    # Test the regular endpoint
    search_url = "http://127.0.0.1:5009/api/inventory/search"

    print(f"\n🔍 Testing regular search for term: '{search_term}'")
    print(f"🔍 Search URL: {search_url}")

    try:
        # Make request to search endpoint
        response = requests.get(search_url, params={'q': search_term, 'limit': 5})

        print(f"🔍 Response status: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"🔍 Response success: {data.get('success', 'Unknown')}")
                print(f"🔍 Items found: {len(data.get('items', []))}")

                # Print items found
                items = data.get('items', [])
                if items:
                    print(f"\n🔍 ITEMS FOUND ({len(items)}):")
                    for i, item in enumerate(items):
                        print(f"  {i+1}. {item.get('itemnum', 'No itemnum')} - {item.get('description', 'No description')}")
                else:
                    print("\n🔍 NO ITEMS FOUND")

            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"❌ Raw response: {response.text[:500]}")
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")

if __name__ == "__main__":
    search_term = sys.argv[1] if len(sys.argv) > 1 else "pump"

    print("=" * 80)
    print("🔍 MATERIAL SEARCH DEBUG TEST")
    print("=" * 80)

    # Test debug endpoint
    test_debug_search(search_term)

    # Test regular endpoint
    test_regular_search(search_term)

    print("\n" + "=" * 80)
    print("🔍 TEST COMPLETE")
    print("=" * 80)
