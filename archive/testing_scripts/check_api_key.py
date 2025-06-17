#!/usr/bin/env python3
"""
Script to check mxapiapikey methods using the logged-in user's OAuth credentials.
"""
import os
import sys
import json
import pickle
import requests
import glob
from urllib.parse import urljoin

def load_oauth_tokens():
    """Load OAuth tokens from the cache."""
    # Path to the token cache - try multiple locations
    cache_dirs = [
        os.path.expanduser("~/.maximo_oauth"),
        os.path.expanduser("~/Desktop/TOKEN/Base/.maximo_oauth"),
        "./.maximo_oauth",
        "/Users/arkprabha/Desktop/TOKEN/Base/.maximo_oauth"
    ]

    # Find all token cache files
    cache_files = []
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            print(f"Checking cache directory: {cache_dir}")
            for root, dirs, files in os.walk(cache_dir):
                for file in files:
                    if file.endswith('.pkl'):
                        cache_files.append(os.path.join(root, file))

    # Also check for flask_session files
    flask_session_dir = "./flask_session"
    if os.path.exists(flask_session_dir):
        print(f"Checking Flask session directory: {flask_session_dir}")
        session_files = glob.glob(f"{flask_session_dir}/*")
        for session_file in session_files:
            if os.path.isfile(session_file):
                cache_files.append(session_file)

    if not cache_files:
        print("No token cache found. Please login first.")
        return None

    print(f"Found {len(cache_files)} potential cache files:")
    for i, file in enumerate(cache_files):
        print(f"{i+1}. {file} (Modified: {os.path.getmtime(file)})")

    # Load the most recent token cache
    latest_cache = max(cache_files, key=os.path.getmtime)
    print(f"\nLoading tokens from: {latest_cache}")

    try:
        with open(latest_cache, 'rb') as f:
            try:
                cached_data = pickle.load(f)

                # Check if this is a Flask session file
                if isinstance(cached_data, dict) and 'access_token' in cached_data:
                    # Direct token cache
                    access_token = cached_data.get('access_token')
                    refresh_token = cached_data.get('refresh_token')
                    base_url = cached_data.get('base_url')
                    username = cached_data.get('username')
                elif isinstance(cached_data, dict) and 'token_manager' in cached_data:
                    # Flask session with token manager
                    token_manager = cached_data.get('token_manager')
                    access_token = token_manager.access_token
                    refresh_token = token_manager.refresh_token
                    base_url = token_manager.base_url
                    username = token_manager.username
                else:
                    # Try to find tokens in the structure
                    print(f"Unexpected cache structure: {type(cached_data)}")
                    print(f"Keys: {cached_data.keys() if isinstance(cached_data, dict) else 'Not a dict'}")

                    # Try to extract from session
                    if isinstance(cached_data, dict):
                        for key, value in cached_data.items():
                            if key == 'username':
                                username = value
                            elif key == 'access_token':
                                access_token = value
                            elif key == 'refresh_token':
                                refresh_token = value
                            elif key == 'base_url':
                                base_url = value

                    # If we couldn't find the tokens, try the next file
                    if 'access_token' not in locals():
                        print("Could not find tokens in this file, trying next...")
                        return load_oauth_tokens_from_files(cache_files[:-1])  # Try remaining files

                print(f"Loaded tokens for user: {username}")
                print(f"Base URL: {base_url}")

                return {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'base_url': base_url,
                    'username': username
                }
            except Exception as e:
                print(f"Error parsing cache file: {e}")
                # Try the next file
                remaining_files = [f for f in cache_files if f != latest_cache]
                if remaining_files:
                    return load_oauth_tokens_from_files(remaining_files)
                return None
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return None

def load_oauth_tokens_from_files(files):
    """Try to load tokens from a list of files."""
    if not files:
        return None

    latest_file = max(files, key=os.path.getmtime)
    print(f"Trying next file: {latest_file}")

    try:
        with open(latest_file, 'rb') as f:
            cached_data = pickle.load(f)

            # Extract tokens (simplified for brevity)
            if isinstance(cached_data, dict):
                access_token = cached_data.get('access_token')
                refresh_token = cached_data.get('refresh_token')
                base_url = cached_data.get('base_url')
                username = cached_data.get('username')

                if access_token and base_url:
                    print(f"Loaded tokens for user: {username}")
                    print(f"Base URL: {base_url}")

                    return {
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'base_url': base_url,
                        'username': username
                    }

            # Try remaining files
            remaining_files = [f for f in files if f != latest_file]
            if remaining_files:
                return load_oauth_tokens_from_files(remaining_files)
            return None
    except Exception as e:
        print(f"Error loading tokens from {latest_file}: {e}")
        # Try remaining files
        remaining_files = [f for f in files if f != latest_file]
        if remaining_files:
            return load_oauth_tokens_from_files(remaining_files)
        return None

def check_api_key_methods(token_data):
    """Check available methods for mxapiapikey."""
    if not token_data:
        return

    base_url = token_data['base_url']
    access_token = token_data['access_token']

    # Create a session with the OAuth token
    session = requests.Session()

    # Set up headers with OAuth token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    # Try to access API key information
    try:
        # First, check if we can access the API key endpoint
        api_key_url = urljoin(base_url, "/oslc/apikey")
        print(f"\nTrying to access API key endpoint: {api_key_url}")

        response = session.get(api_key_url, headers=headers)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                print("API Key endpoint response:")
                print(json.dumps(data, indent=2))
            except:
                print("Response is not JSON format")
                print(response.text[:500])  # Print first 500 chars
        else:
            print(f"Failed to access API key endpoint: {response.text[:500]}")

        # Try to list available methods
        methods_url = urljoin(base_url, "/oslc/apikey/methods")
        print(f"\nTrying to access API key methods: {methods_url}")

        response = session.get(methods_url, headers=headers)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                print("API Key methods response:")
                print(json.dumps(data, indent=2))
            except:
                print("Response is not JSON format")
                print(response.text[:500])  # Print first 500 chars
        else:
            print(f"Failed to access API key methods: {response.text[:500]}")

        # Try to check if mmxapiapikey is available
        print("\nChecking for mmxapiapikey in headers...")
        headers_url = urljoin(base_url, "/oslc/whoami")

        # Try with mmxapiapikey header (empty value just to test)
        test_headers = headers.copy()
        test_headers["mmxapiapikey"] = "test"

        response = session.get(headers_url, headers=test_headers)
        print(f"Status code with mmxapiapikey header: {response.status_code}")

        if response.status_code == 200:
            print("mmxapiapikey header accepted")
        else:
            print(f"mmxapiapikey header rejected: {response.text[:500]}")

    except Exception as e:
        print(f"Error checking API key methods: {e}")

if __name__ == "__main__":
    print("Checking mxapiapikey methods using logged-in user's OAuth credentials...")
    token_data = load_oauth_tokens()
    check_api_key_methods(token_data)
