#!/usr/bin/env python3
"""
Simple script to query the MXAPIWODETAIL endpoint.
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    print("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def query_wodetail():
    """Query the MXAPIWODETAIL endpoint."""
    endpoint = f"{BASE_URL}/api/os/mxapiwodetail"
    
    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": "10",  # Limit to 10 records
        "oslc.select": "*"  # Request all fields
    }
    
    # Prepare headers
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY
    }
    
    # Get username from environment if available
    username = os.getenv('MAXIMO_USERNAME', '')
    if username:
        headers["x-user-context"] = username
    
    try:
        # Make the API request
        print(f"Querying {endpoint}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        print(f"Query parameters: {json.dumps(query_params, indent=2)}")
        
        response = requests.get(
            endpoint,
            params=query_params,
            headers=headers,
            timeout=(3.05, 15)  # Connection timeout, read timeout
        )
        
        # Check for successful response
        if response.status_code == 200:
            print(f"Successfully fetched work order data. Status code: {response.status_code}")
            
            # Save the raw response for debugging
            with open('wodetail_raw_response.json', 'w') as f:
                f.write(response.text)
            
            # Parse the JSON response
            try:
                data = response.json()
                
                # Check for member key
                if 'member' in data:
                    print(f"Found {len(data['member'])} work order records")
                    
                    # Print the first record
                    if data['member']:
                        print("\nFirst record keys:")
                        for key in data['member'][0].keys():
                            print(f"  {key}")
                        
                        # Check for nested structures
                        print("\nNested structures:")
                        for key, value in data['member'][0].items():
                            if isinstance(value, (list, dict)):
                                print(f"  {key}: {type(value).__name__}")
                                if isinstance(value, list) and value:
                                    print(f"    First item type: {type(value[0]).__name__}")
                                    if isinstance(value[0], dict):
                                        print(f"    First item keys: {list(value[0].keys())}")
                elif 'rdfs:member' in data:
                    print(f"Found {len(data['rdfs:member'])} work order records")
                else:
                    print(f"No member data found in response. Keys: {list(data.keys())}")
                    
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                print(f"Response text: {response.text[:500]}")
        else:
            print(f"Error fetching work order data. Status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Exception during request: {str(e)}")

if __name__ == "__main__":
    query_wodetail()
