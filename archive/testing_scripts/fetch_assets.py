#!/usr/bin/env python3
"""
Script to fetch operating assets for the logged-in user's default site using API key.
This script will:
1. Load the logged-in user's OAuth credentials
2. Generate/retrieve an API key using those credentials
3. Use the API key to fetch asset data
"""
import os
import sys
import json
import pickle
import requests
import time
import glob
from urllib.parse import urljoin

# Base URL for Maximo
BASE_URL = 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo'

def load_user_profile():
    """Load the logged-in user's profile from cache."""
    # Path to the token cache - try multiple locations
    cache_dirs = [
        os.path.expanduser("~/.maximo_oauth"),
        os.path.expanduser("~/Desktop/TOKEN/Base/.maximo_oauth"),
        "./.maximo_oauth",
        "/Users/arkprabha/Desktop/TOKEN/Base/.maximo_oauth"
    ]

    # Find all profile cache files
    profile_files = []
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            print(f"Checking cache directory: {cache_dir}")
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    if file.startswith('profile_') and file.endswith('.pkl'):
                        profile_files.append(os.path.join(root, file))

    if not profile_files:
        print("No profile cache found. Please login first.")
        return None

    print(f"Found {len(profile_files)} profile cache files:")
    for i, file in enumerate(profile_files):
        print(f"{i+1}. {file} (Modified: {os.path.getmtime(file)})")

    # Load the most recent profile cache
    latest_profile = max(profile_files, key=os.path.getmtime)
    print(f"\nLoading profile from: {latest_profile}")

    try:
        with open(latest_profile, 'rb') as f:
            profile_data = pickle.load(f)

            # Extract profile information
            if isinstance(profile_data, dict) and 'profile' in profile_data:
                username = profile_data.get('username')
                profile = profile_data.get('profile', {})
                print(f"Loaded profile for user: {username}")
                return profile
            else:
                print(f"Unexpected profile structure: {type(profile_data)}")
                return None
    except Exception as e:
        print(f"Error loading profile: {e}")
        return None

def load_oauth_tokens():
    """Load OAuth tokens from the cache."""
    # Path to the token cache - try multiple locations
    cache_dirs = [
        os.path.expanduser("~/.maximo_oauth"),
        os.path.expanduser("~/Desktop/TOKEN/Base/.maximo_oauth"),
        "./.maximo_oauth",
        "/Users/arkprabha/Desktop/TOKEN/Base/.maximo_oauth"
    ]

    # Also check for flask_session files
    flask_session_dir = "./flask_session"
    if os.path.exists(flask_session_dir):
        cache_dirs.append(flask_session_dir)

    # Find all token cache files
    token_files = []
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            print(f"Checking cache directory: {cache_dir}")
            if cache_dir == flask_session_dir:
                # Flask session files don't have a standard naming convention
                session_files = glob.glob(f"{cache_dir}/*")
                for session_file in session_files:
                    if os.path.isfile(session_file):
                        token_files.append(session_file)
            else:
                # Look for token cache files
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        if file.endswith('.pkl') and not file.startswith('profile_'):
                            token_files.append(os.path.join(root, file))

    if not token_files:
        print("No token cache found. Please login first.")
        return None

    print(f"Found {len(token_files)} potential token cache files:")
    for i, file in enumerate(token_files):
        print(f"{i+1}. {file} (Modified: {os.path.getmtime(file)})")

    # Load the most recent token cache
    latest_token = max(token_files, key=os.path.getmtime)
    print(f"\nLoading tokens from: {latest_token}")

    try:
        with open(latest_token, 'rb') as f:
            cached_data = pickle.load(f)

            # Try to extract tokens from various cache formats
            access_token = None
            refresh_token = None
            username = None

            # Check if this is a direct token cache
            if isinstance(cached_data, dict):
                if 'access_token' in cached_data:
                    access_token = cached_data.get('access_token')
                    refresh_token = cached_data.get('refresh_token')
                    username = cached_data.get('username')
                elif 'token_manager' in cached_data:
                    # Flask session with token manager
                    token_manager = cached_data.get('token_manager')
                    if hasattr(token_manager, 'access_token'):
                        access_token = token_manager.access_token
                        refresh_token = token_manager.refresh_token
                        username = token_manager.username

            if access_token and username:
                print(f"Loaded tokens for user: {username}")
                return {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'username': username
                }
            else:
                print(f"Could not find tokens in cache file")
                return None
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return None

def generate_api_key(oauth_tokens):
    """Generate or retrieve an API key using OAuth credentials.

    Args:
        oauth_tokens (dict): OAuth tokens

    Returns:
        str: API key
    """
    if not oauth_tokens or 'access_token' not in oauth_tokens:
        print("Error: No OAuth tokens available")
        return None

    # Create session for requests
    session = requests.Session()

    # Prepare API endpoint for API key generation/retrieval
    apikey_url = f"{BASE_URL}/oslc/apikey"

    # Prepare headers with OAuth token
    headers = {
        "Authorization": f"Bearer {oauth_tokens['access_token']}",
        "Accept": "application/json"
    }

    print(f"\nGenerating/retrieving API key using OAuth credentials...")
    print(f"API URL: {apikey_url}")

    try:
        # Make the API request to get API key
        response = session.get(
            apikey_url,
            headers=headers,
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
                    return create_new_api_key(oauth_tokens)
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
                return None
        else:
            print(f"Error retrieving API key. Status code: {response.status_code}")
            print(f"Response text: {response.text[:500]}")

            # If 404, the endpoint might not exist or the user doesn't have an API key yet
            if response.status_code == 404:
                return create_new_api_key(oauth_tokens)
            return None
    except Exception as e:
        print(f"Exception during API key retrieval: {e}")
        return None

def create_new_api_key(oauth_tokens):
    """Create a new API key using OAuth credentials.

    Args:
        oauth_tokens (dict): OAuth tokens

    Returns:
        str: New API key
    """
    if not oauth_tokens or 'access_token' not in oauth_tokens:
        print("Error: No OAuth tokens available")
        return None

    # Create session for requests
    session = requests.Session()

    # Prepare API endpoint for API key creation
    apikey_url = f"{BASE_URL}/oslc/apikey"

    # Prepare headers with OAuth token
    headers = {
        "Authorization": f"Bearer {oauth_tokens['access_token']}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Prepare request body
    # Note: The actual structure depends on the Maximo API requirements
    request_body = {
        "description": f"Auto-generated API key for {oauth_tokens['username']} - {time.strftime('%Y-%m-%d %H:%M:%S')}",
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
    assets_url = f"{BASE_URL}/api/os/mxapiasset"

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

    # Step 1: Load OAuth tokens
    oauth_tokens = load_oauth_tokens()

    if not oauth_tokens:
        print("Error: Could not load OAuth tokens. Please login first.")
        sys.exit(1)

    print(f"User: {oauth_tokens['username']}")

    # Step 2: Load user profile to get default site
    user_profile = load_user_profile()

    if not user_profile:
        print("Error: Could not load user profile. Please login first.")
        sys.exit(1)

    # Get default site from user profile
    default_site = user_profile.get('defaultSite')
    username = user_profile.get('loginUserName') or oauth_tokens['username']

    if not default_site:
        print("Error: No default site found in user profile.")
        sys.exit(1)

    print(f"Default Site: {default_site}")

    # Step 3: Generate/retrieve API key using OAuth credentials
    api_key = generate_api_key(oauth_tokens)

    if not api_key:
        print("Error: Could not generate/retrieve API key.")
        sys.exit(1)

    # Step 4: Fetch assets using the API key
    assets_data = fetch_assets_with_api_key(default_site, username, api_key)

    # Step 5: Display assets
    display_assets(assets_data)
