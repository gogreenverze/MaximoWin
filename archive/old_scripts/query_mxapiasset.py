#!/usr/bin/env python3
"""
Script to query the MXAPIASSET endpoint and analyze its structure.
This script will:
1. Load API key from .env file
2. Query the MXAPIASSET endpoint with minimal filters
3. Print the structure of the response
4. Save the raw response to a file for further analysis
"""
import os
import sys
import json
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('query_mxapiasset')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def query_mxapiasset():
    """
    Query the MXAPIASSET endpoint and analyze its structure.
    """
    # Try both API endpoint formats
    endpoints = [
        f"{BASE_URL}/api/os/mxapiasset",  # Standard REST API format
        f"{BASE_URL}/oslc/os/mxapiasset"  # OSLC format
    ]

    # Prepare query parameters - keep it simple
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": "5",  # Limit to 5 records for analysis
        "oslc.select": "*",  # Request all fields
        "oslc.where": "status=\"OPERATING\""  # Filter for operating assets
    }

    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY
    }

    # Try each endpoint
    for endpoint in endpoints:
        logger.info(f"Trying endpoint: {endpoint}")
        logger.info(f"Using query parameters: {json.dumps(query_params, indent=2)}")

        try:
            # Make the API request
            response = requests.get(
                endpoint,
                params=query_params,
                headers=headers,
                timeout=(3.05, 30)  # Connection timeout, read timeout
            )

            # Check for successful response
            if response.status_code == 200:
                logger.info(f"Successfully queried MXAPIASSET. Status code: {response.status_code}")

                # Save the raw response for further analysis
                with open('mxapiasset_response.json', 'w') as f:
                    f.write(response.text)

                # Parse the JSON response
                try:
                    data = response.json()

                    # Check for member key
                    if 'member' in data:
                        logger.info(f"Found {len(data['member'])} asset records")

                        # Analyze the first record
                        if data['member']:
                            first_record = data['member'][0]

                            # Print the structure directly
                            print("\n=== MXAPIASSET STRUCTURE ===\n")
                            print(json.dumps(first_record, indent=2)[:2000])  # Print first 2000 chars
                            print("... (truncated)")

                            # Save the first record for detailed analysis
                            with open('mxapiasset_first_record.json', 'w') as f:
                                json.dump(first_record, f, indent=2)

                            logger.info("Saved first record to mxapiasset_first_record.json")

                        return data
                    elif 'rdfs:member' in data:
                        logger.info(f"Found {len(data['rdfs:member'])} asset records")
                        # Standardize the data structure
                        data['member'] = data['rdfs:member']
                        return data
                    else:
                        logger.warning(f"No member data found in response. Keys: {list(data.keys())}")
                        continue

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
                    logger.warning(f"Response text: {response.text[:500]}")
                    continue
            else:
                logger.warning(f"Error querying MXAPIASSET. Status code: {response.status_code}")
                logger.warning(f"Response: {response.text[:500]}")
                continue

        except Exception as e:
            logger.warning(f"Exception during request: {str(e)}")
            continue

    logger.error("All endpoints failed")
    return None

def main():
    """Main function to query MXAPIASSET and analyze its structure."""
    data = query_mxapiasset()

    if not data:
        logger.error("Failed to query MXAPIASSET")
        return

    # Print summary
    print("\n=== MXAPIASSET QUERY SUMMARY ===\n")
    print(f"Total records: {len(data.get('member', []))}")
    print(f"Response saved to: mxapiasset_response.json")
    print(f"First record saved to: mxapiasset_first_record.json")
    print("\nReview these files to understand the structure of the MXAPIASSET endpoint.")

if __name__ == "__main__":
    main()
