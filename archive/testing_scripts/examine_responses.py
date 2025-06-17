#!/usr/bin/env python3
"""
Script to examine responses from Maximo API with different authentication methods.
"""
import os
import sys
import json
import hashlib
import time
import requests

# Base URL for Maximo
BASE_URL = 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo'

def examine_responses():
    """Examine responses from Maximo API with different authentication methods."""
    # Generate a test API key
    username = "megan.sofge@vectrus.com"  # Example username
    date_str = time.strftime("%Y-%m-%d")
    api_key_seed = f"{username}:{date_str}:maximo_test_key"
    generated_api_key = hashlib.sha256(api_key_seed.encode()).hexdigest()
    
    print(f"Generated API key: {generated_api_key[:10]}...{generated_api_key[-10:]}")
    
    # Test endpoints
    endpoints = [
        {
            'name': 'WhoAmI',
            'url': f"{BASE_URL}/oslc/whoami",
            'params': {}
        },
        {
            'name': 'Assets (mxapiasset)',
            'url': f"{BASE_URL}/api/os/mxapiasset",
            'params': {
                'lean': '1',
                'oslc.select': 'assetnum,description,status,siteid',
                'oslc.where': 'status="OPERATING"',
                'oslc.pageSize': '10'
            }
        }
    ]
    
    # Test with different headers
    header_sets = [
        {
            'name': 'No Auth',
            'headers': {
                'Accept': 'application/json'
            }
        },
        {
            'name': 'mxapiapikey',
            'headers': {
                'Accept': 'application/json',
                'mxapiapikey': generated_api_key
            }
        },
        {
            'name': 'mxapiapikey with user context',
            'headers': {
                'Accept': 'application/json',
                'mxapiapikey': generated_api_key,
                'x-user-context': username
            }
        }
    ]
    
    # Run tests
    for endpoint in endpoints:
        print(f"\n=== Testing endpoint: {endpoint['name']} ===")
        
        for header_set in header_sets:
            print(f"\n  Using {header_set['name']} headers:")
            
            try:
                start_time = time.time()
                response = requests.get(
                    endpoint['url'],
                    params=endpoint['params'],
                    headers=header_set['headers'],
                    timeout=(3.05, 15)
                )
                elapsed_time = time.time() - start_time
                
                print(f"  Status code: {response.status_code}")
                print(f"  Response time: {elapsed_time:.2f} seconds")
                print(f"  Response headers: {dict(response.headers)}")
                
                # Check if response is HTML (likely a redirect to login page)
                content_type = response.headers.get('Content-Type', '')
                if 'html' in content_type.lower():
                    print(f"  Response appears to be HTML (likely a login page)")
                    print(f"  First 200 characters: {response.text[:200]}...")
                else:
                    # Try to parse as JSON
                    try:
                        data = response.json()
                        print(f"  Response is valid JSON")
                        if 'member' in data:
                            print(f"  Found {len(data['member'])} items")
                            if len(data['member']) > 0:
                                print(f"  First item: {json.dumps(data['member'][0], indent=2)[:200]}...")
                        else:
                            print(f"  Response keys: {list(data.keys())}")
                            print(f"  Response content: {json.dumps(data, indent=2)[:200]}...")
                    except Exception as e:
                        print(f"  Error parsing JSON: {e}")
                        print(f"  Raw response (first 200 chars): {response.text[:200]}...")
                
                print(f"  Full URL with params: {response.url}")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    print("Examining responses from Maximo API with different authentication methods...")
    examine_responses()
