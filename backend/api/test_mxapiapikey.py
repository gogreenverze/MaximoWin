#!/usr/bin/env python3
"""
Script to test the mxapiapikey header for accessing Maximo API.
"""
import os
import sys
import json
import hashlib
import time
import requests

# Base URL for Maximo
BASE_URL = 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo'

def test_mxapiapikey():
    """Test the mxapiapikey header for accessing Maximo API."""
    # Generate a test API key
    username = "megan.sofge@vectrus.com"  # Example username
    date_str = time.strftime("%Y-%m-%d")
    api_key_seed = f"{username}:{date_str}:maximo_test_key"
    generated_api_key = hashlib.sha256(api_key_seed.encode()).hexdigest()
    
    print(f"Generated API key: {generated_api_key[:10]}...{generated_api_key[-10:]}")
    
    # Test endpoints
    endpoints = [
        {
            'name': 'Assets (mxapiasset)',
            'url': f"{BASE_URL}/api/os/mxapiasset",
            'params': {
                'lean': '1',
                'oslc.select': 'assetnum,description,status,siteid',
                'oslc.where': 'status="OPERATING"',
                'oslc.pageSize': '10'
            }
        },
        {
            'name': 'Users (mxuser)',
            'url': f"{BASE_URL}/api/os/mxuser",
            'params': {
                'lean': '1',
                'oslc.select': 'loginid,person.displayname,status',
                'oslc.pageSize': '10'
            }
        },
        {
            'name': 'Sites',
            'url': f"{BASE_URL}/oslc/sites",
            'params': {}
        },
        {
            'name': 'WhoAmI',
            'url': f"{BASE_URL}/oslc/whoami",
            'params': {}
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
    results = []
    
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
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if 'member' in data:
                            print(f"  Found {len(data['member'])} items")
                        else:
                            print(f"  Response keys: {list(data.keys())}")
                    except Exception as e:
                        print(f"  Error parsing JSON: {e}")
                else:
                    print(f"  Response text: {response.text[:100]}...")
                
                results.append({
                    'endpoint': endpoint['name'],
                    'auth_method': header_set['name'],
                    'status_code': response.status_code,
                    'response_time': elapsed_time,
                    'success': response.status_code == 200
                })
            except Exception as e:
                print(f"  Error: {e}")
                results.append({
                    'endpoint': endpoint['name'],
                    'auth_method': header_set['name'],
                    'error': str(e),
                    'success': False
                })
    
    # Print summary
    print("\n=== Summary ===")
    success_count = sum(1 for r in results if r.get('success', False))
    print(f"Total tests: {len(results)}")
    print(f"Successful tests: {success_count}")
    print(f"Failed tests: {len(results) - success_count}")
    
    # Print success rate by auth method
    print("\nSuccess rate by auth method:")
    for header_set in header_sets:
        method_results = [r for r in results if r.get('auth_method') == header_set['name']]
        method_success = sum(1 for r in method_results if r.get('success', False))
        if method_results:
            success_rate = method_success / len(method_results) * 100
            print(f"  {header_set['name']}: {success_rate:.1f}% ({method_success}/{len(method_results)})")
    
    return results

if __name__ == "__main__":
    print("Testing mxapiapikey header for accessing Maximo API...")
    test_mxapiapikey()
