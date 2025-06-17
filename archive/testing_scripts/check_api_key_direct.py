#!/usr/bin/env python3
"""
Script to check mxapiapikey methods by directly accessing the running Flask app.
"""
import os
import sys
import json
import requests
from urllib.parse import urljoin

# Define the base URL of the Maximo server
MAXIMO_BASE_URL = "https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo"

def check_api_key_methods():
    """Check available methods for mxapiapikey by using the Flask app's session."""
    # First, get the session cookie from the Flask app
    flask_app_url = "http://127.0.0.1:5004"
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Get the session cookie
    print("Getting session cookie from Flask app...")
    response = session.get(f"{flask_app_url}/api/auth-status")
    
    if response.status_code != 200:
        print(f"Failed to get session cookie: {response.status_code}")
        print(response.text)
        return
    
    # Check if we're logged in
    auth_status = response.json()
    print(f"Auth status: {auth_status}")
    
    if not auth_status.get("authenticated", False):
        print("Not logged in. Please login first.")
        return
    
    # Get the username
    username = auth_status.get("username")
    print(f"Logged in as: {username}")
    
    # Now try to access the Maximo API directly using the session cookie
    # This works because the Flask app has set the necessary cookies in our session
    
    # Try to access the whoami endpoint to verify our session
    whoami_url = f"{MAXIMO_BASE_URL}/oslc/whoami"
    print(f"\nTrying to access whoami endpoint: {whoami_url}")
    
    headers = {
        "Accept": "application/json"
    }
    
    try:
        response = session.get(whoami_url, headers=headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("Whoami response:")
                print(json.dumps(data, indent=2)[:500])  # Print first 500 chars
            except:
                print("Response is not JSON format")
                print(response.text[:500])  # Print first 500 chars
        else:
            print(f"Failed to access whoami endpoint: {response.text[:500]}")
    except Exception as e:
        print(f"Error accessing whoami endpoint: {e}")
    
    # Now try to check if mmxapiapikey is available
    print("\nChecking for mmxapiapikey in headers...")
    
    # Try with mmxapiapikey header (empty value just to test)
    test_headers = headers.copy()
    test_headers["mmxapiapikey"] = "test"
    
    try:
        response = session.get(whoami_url, headers=test_headers)
        print(f"Status code with mmxapiapikey header: {response.status_code}")
        
        if response.status_code == 200:
            print("mmxapiapikey header accepted")
            try:
                data = response.json()
                print("Response with mmxapiapikey:")
                print(json.dumps(data, indent=2)[:500])  # Print first 500 chars
            except:
                print("Response is not JSON format")
                print(response.text[:500])  # Print first 500 chars
        else:
            print(f"mmxapiapikey header rejected: {response.text[:500]}")
    except Exception as e:
        print(f"Error with mmxapiapikey header: {e}")
    
    # Try to access the API using the REST API endpoint with mmxapiapikey
    rest_url = f"{MAXIMO_BASE_URL}/api/os/mxuser"
    print(f"\nTrying to access REST API endpoint with mmxapiapikey: {rest_url}")
    
    rest_headers = {
        "Accept": "application/json",
        "mmxapiapikey": "test"
    }
    
    try:
        response = session.get(rest_url, headers=rest_headers)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("REST API with mmxapiapikey successful")
            try:
                data = response.json()
                print("Response:")
                print(json.dumps(data, indent=2)[:500])  # Print first 500 chars
            except:
                print("Response is not JSON format")
                print(response.text[:500])  # Print first 500 chars
        else:
            print(f"REST API with mmxapiapikey failed: {response.text[:500]}")
    except Exception as e:
        print(f"Error accessing REST API with mmxapiapikey: {e}")

if __name__ == "__main__":
    print("Checking mxapiapikey methods using the Flask app's session...")
    check_api_key_methods()
