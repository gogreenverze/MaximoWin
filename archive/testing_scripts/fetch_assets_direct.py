#!/usr/bin/env python3
"""
Script to fetch operating assets for the logged-in user's default site using API key.
This script will:
1. Access the token_manager directly from the Flask app
2. Use the token_manager to make API calls
3. Display the results in the terminal
"""
import os
import sys
import json
import requests
import time
from urllib.parse import urljoin

# Import the token_manager from the Flask app
try:
    from app import token_manager
except ImportError:
    print("Error: Could not import token_manager from app.py")
    print("Make sure the Flask app is running and you're in the correct directory.")
    sys.exit(1)

def check_login():
    """Check if the user is logged in."""
    if not token_manager.is_logged_in():
        print("Error: Not logged in. Please login first.")
        return False
    
    print(f"Logged in as: {token_manager.username}")
    return True

def get_user_profile():
    """Get the user profile using the token_manager."""
    try:
        # Use the token_manager to get the user profile
        user_profile = token_manager.get_user_profile(use_mock=False, use_cache=True)
        
        if not user_profile:
            print("Error: Could not get user profile.")
            return None
        
        # Get default site from user profile
        default_site = user_profile.get('defaultSite')
        
        if not default_site:
            print("Error: No default site found in user profile.")
            return None
        
        print(f"Default Site: {default_site}")
        return user_profile
    except Exception as e:
        print(f"Error getting user profile: {e}")
        return None

def generate_api_key():
    """Generate or retrieve an API key using the token_manager's session."""
    if not token_manager.is_logged_in():
        print("Error: Not logged in.")
        return None
    
    # Prepare API endpoint for API key generation/retrieval
    apikey_url = f"{token_manager.base_url}/oslc/apikey"
    
    # Use the token_manager's session which already has the OAuth credentials
    session = token_manager.session
    
    print(f"\nGenerating/retrieving API key...")
    print(f"API URL: {apikey_url}")
    
    try:
        # Make the API request to get API key
        response = session.get(
            apikey_url,
            headers={"Accept": "application/json"},
            timeout=(3.05, 15)  # Timeout values
        )
        
        # Check response
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Successfully retrieved API key information. Status code: {response.status_code}")
                
                # Extract API key from response
                # Note: The actual structure depends on the Maximo API response
                if 'apikey' in data:
                    api_key = data['apikey']
                    print("API key retrieved successfully")
                    return api_key
                else:
                    print(f"API key not found in response. Response keys: {data.keys()}")
                    print(f"Response: {json.dumps(data, indent=2)[:500]}")
                    
                    # Try to create a new API key if not found
                    return create_new_api_key()
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
                return None
        else:
            print(f"Error retrieving API key. Status code: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            
            # If 404, the endpoint might not exist or the user doesn't have an API key yet
            if response.status_code == 404:
                return create_new_api_key()
            return None
    except Exception as e:
        print(f"Exception during API key retrieval: {e}")
        return None

def create_new_api_key():
    """Create a new API key using the token_manager's session."""
    if not token_manager.is_logged_in():
        print("Error: Not logged in.")
        return None
    
    # Prepare API endpoint for API key creation
    apikey_url = f"{token_manager.base_url}/oslc/apikey"
    
    # Use the token_manager's session which already has the OAuth credentials
    session = token_manager.session
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Prepare request body
    # Note: The actual structure depends on the Maximo API requirements
    request_body = {
        "description": f"Auto-generated API key for {token_manager.username} - {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "expiration": None  # No expiration
    }
    
    print(f"\nCreating new API key...")
    print(f"API URL: {apikey_url}")
    
    try:
        # Make the API request to create API key
        response = session.post(
            apikey_url,
            headers=headers,
            json=request_body,
            timeout=(3.05, 15)  # Timeout values
        )
        
        # Check response
        if response.status_code in [200, 201]:
            try:
                data = response.json()
                print(f"Successfully created API key. Status code: {response.status_code}")
                
                # Extract API key from response
                # Note: The actual structure depends on the Maximo API response
                if 'apikey' in data:
                    api_key = data['apikey']
                    print("New API key created successfully")
                    return api_key
                else:
                    print(f"API key not found in response. Response keys: {data.keys()}")
                    print(f"Response: {json.dumps(data, indent=2)[:500]}")
                    return None
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
                return None
        else:
            print(f"Error creating API key. Status code: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            return None
    except Exception as e:
        print(f"Exception during API key creation: {e}")
        return None

def fetch_assets_with_api_key(default_site, username, api_key):
    """Fetch operating assets for the user's default site using API key.
    
    Args:
        default_site (str): User's default site
        username (str): Username for context
        api_key (str): API key for authentication
        
    Returns:
        list: List of assets
    """
    if not api_key:
        print("Error: No API key available")
        return None
        
    if not default_site:
        print("Error: No default site found for user")
        return None
    
    # Create session for requests
    session = requests.Session()
    
    # Prepare API endpoint for assets
    assets_url = f"{token_manager.base_url}/api/os/mxapiasset"
    
    # Prepare query parameters to filter assets
    # Filter for operating assets in the user's default site
    query_params = {
        "lean": "1",  # Get lean response for better performance
        "oslc.select": "assetnum,description,status,siteid",  # Select specific fields
        "oslc.where": f"status=\"OPERATING\" and siteid=\"{default_site}\"",  # Filter criteria
        "oslc.pageSize": "100"  # Limit results
    }
    
    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "mmxapiapikey": api_key,
        "x-user-context": username  # Include user context
    }
    
    print(f"\nFetching assets for site {default_site} with status OPERATING...")
    print(f"API URL: {assets_url}")
    print(f"Query parameters: {query_params}")
    
    try:
        # Make the API request
        response = session.get(
            assets_url,
            params=query_params,
            headers=headers,
            timeout=(3.05, 15)  # Timeout values
        )
        
        # Check response
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Successfully fetched assets. Status code: {response.status_code}")
                return data
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
                return None
        else:
            print(f"Error fetching assets. Status code: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            return None
    except Exception as e:
        print(f"Exception during API request: {e}")
        return None

def display_assets(assets_data):
    """Display assets in a formatted table in the terminal.
    
    Args:
        assets_data (dict): Asset data from API
    """
    if not assets_data:
        print("No asset data to display")
        return
    
    # Extract the member array from the response
    try:
        if 'member' in assets_data:
            assets = assets_data['member']
            asset_count = len(assets)
            
            if asset_count == 0:
                print("No assets found matching the criteria")
                return
                
            print(f"\nFound {asset_count} operating assets:")
            
            # Print header
            header = f"{'ASSET NUM':<15} {'SITE ID':<10} {'STATUS':<15} {'DESCRIPTION':<50}"
            print("\n" + "=" * 90)
            print(header)
            print("-" * 90)
            
            # Print each asset
            for asset in assets:
                asset_num = asset.get('assetnum', 'N/A')
                site_id = asset.get('siteid', 'N/A')
                status = asset.get('status', 'N/A')
                description = asset.get('description', 'N/A')
                
                # Truncate description if too long
                if len(description) > 47:
                    description = description[:47] + "..."
                
                row = f"{asset_num:<15} {site_id:<10} {status:<15} {description:<50}"
                print(row)
            
            print("=" * 90)
        else:
            print("Unexpected response format. 'member' array not found.")
            print(f"Response keys: {assets_data.keys()}")
    except Exception as e:
        print(f"Error displaying assets: {e}")

if __name__ == "__main__":
    print("Fetching operating assets for logged-in user's default site using API key...")
    
    # Step 1: Check if the user is logged in
    if not check_login():
        sys.exit(1)
    
    # Step 2: Get the user profile
    user_profile = get_user_profile()
    
    if not user_profile:
        sys.exit(1)
    
    # Get default site and username
    default_site = user_profile.get('defaultSite')
    username = user_profile.get('loginUserName') or token_manager.username
    
    # Step 3: Generate/retrieve API key
    api_key = generate_api_key()
    
    if not api_key:
        print("Error: Could not generate/retrieve API key.")
        sys.exit(1)
    
    # Step 4: Fetch assets using the API key
    assets_data = fetch_assets_with_api_key(default_site, username, api_key)
    
    # Step 5: Display assets
    display_assets(assets_data)
