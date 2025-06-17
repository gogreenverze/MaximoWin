#!/usr/bin/env python3
"""
Test script to demonstrate the functionality of token_sites.py
"""
import sys
import json
from token_sites import MaximoSitesManager
from token_manager import MaximoTokenManager

# Create an instance of the token manager
# Note: This will only work if you're already logged in
try:
    # Try to use the token manager from the app if it exists
    from app import token_manager
    print("Using token_manager from app")
except ImportError:
    # Otherwise create a new instance
    print("Creating new token_manager instance")
    # You may need to adjust the base URL to match your Maximo instance
    token_manager = MaximoTokenManager(base_url="https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo")

# Check if we're logged in
print(f"Logged in: {token_manager.is_logged_in()}")

# Get available sites
print("\nGetting available sites...")
sites = token_manager.get_available_sites(use_mock=False, use_cache=True)

# Print the results
print(f"\nFound {len(sites)} sites:")
for site in sites:
    print(f"  - {site['siteid']}: {site.get('description', 'No description')}")

# Get user profile
print("\nGetting user profile...")
try:
    profile = token_manager.get_user_profile(False)
    if profile:
        print(f"User: {profile.get('displayName', 'Unknown')}")
        print(f"Default site: {profile.get('defaultSite', profile.get('spi:defaultSite', 'Unknown'))}")
    else:
        print("No profile information available")
except Exception as e:
    print(f"Error getting profile: {e}")
