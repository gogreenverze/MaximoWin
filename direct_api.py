import os
import requests
import json
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key and URL from environment
MAXIMO_API_KEY = os.getenv('MAXIMO_API_KEY')
MAXIMO_URL = os.getenv('MAXIMO_URL')
MAXIMO_VERIFY_SSL = os.getenv('MAXIMO_VERIFY_SSL', 'True').lower() == 'true'

if not MAXIMO_API_KEY:
    raise ValueError("MAXIMO_API_KEY not found in .env file")
if not MAXIMO_URL:
    raise ValueError("MAXIMO_URL not found in .env file")

def decode_site_id(resource_url):
    """Extract and decode the site ID from the resource URL"""
    try:
        # Extract the last part of the URL after the last slash
        encoded_id = resource_url.split('/')[-1]
        # Remove the leading underscore if present
        if encoded_id.startswith('_'):
            encoded_id = encoded_id[1:]
        # Decode the base64 string
        decoded = base64.b64decode(encoded_id).decode('utf-8')
        return decoded
    except Exception as e:
        print(f"Error decoding site ID: {str(e)}")
        return None

def get_site_details(user_id):
    """Get site details using SQL query through mxapisite endpoint"""
    url = f"{MAXIMO_URL}/api/os/mxapisite"
    
    # SQL query to get site details
    sql_query = f"""
    SELECT s.*, m.description as group_description 
    FROM SITEAUTH s 
    JOIN maxgroup m ON s.groupname = m.groupname
    WHERE s.groupname IN (
        SELECT groupname
        FROM maxgroup
        WHERE EXISTS (
            SELECT 1
            FROM groupuser
            WHERE userid = '{user_id}'
            AND groupuser.groupname = maxgroup.groupname
        )
    )
    """
    
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'apikey': MAXIMO_API_KEY
    }
    
    params = {
        '_sql': sql_query,
        '_format': 'json',
        '_compact': 'false'
    }
    
    try:
        print(f"Making request to: {url}")
        print(f"Using SQL Query: {sql_query}")
        response = requests.get(url, headers=headers, params=params, verify=MAXIMO_VERIFY_SSL)
        print(f"\nStatus Code: {response.status_code}")
        
        try:
            json_response = response.json()
            print(f"\nFull JSON Response Structure:\n{json.dumps(json_response, indent=2)[:2000]}")
            # After printing, you can comment out or remove the above line once you know the structure
            # Now, try to extract site details from the correct key
            if isinstance(json_response, dict):
                for key in json_response:
                    print(f"Top-level key: {key}")
            if 'rdf:resource' in json_response:
                # Process only the first 3 site resources for demonstration
                for i, resource in enumerate(json_response['rdf:resource']):
                    if i >= 3:
                        break
                    print(f"Resource entry type: {type(resource)}; value: {resource}")
                    # Try to extract the URL from the resource entry
                    if isinstance(resource, dict) and 'rdf:resource' in resource:
                        site_url = resource['rdf:resource']
                    elif isinstance(resource, str):
                        site_url = resource
                    else:
                        print(f"Unexpected resource entry format: {resource}")
                        continue
                    site_id = decode_site_id(site_url)
                    print(f"Resource URL: {site_url}")
                    print(f"Decoded Site ID: {site_id}")
                    if site_id:
                        # Get detailed information for this site
                        site_details_url = f"{MAXIMO_URL}/api/os/mxapisite/{site_id}"
                        site_response = requests.get(site_details_url, headers=headers, verify=MAXIMO_VERIFY_SSL)
                        if site_response.status_code == 200:
                            site_data = site_response.json()
                            print(f"Site Details: {json.dumps(site_data, indent=2)[:2000]}")
                        else:
                            print(f"Failed to get details for site {site_id}: {site_response.status_code}")
            else:
                print(f"\nResponse Body: {json.dumps(json_response, indent=2)}")
        except json.JSONDecodeError:
            print(f"\nRaw Response Body: {response.text[:1000]}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {str(e)}")
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")

if __name__ == "__main__":
    # Extract user ID from terminal output
    user_id = "TINU.THOMAS"  # The user ID from the terminal output
    get_site_details(user_id) 