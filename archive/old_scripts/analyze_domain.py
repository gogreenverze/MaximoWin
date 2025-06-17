#!/usr/bin/env python3
"""
Script to analyze the MXDOMAIN endpoint structure.
This script will:
1. Load API key from .env file
2. Fetch data from MXDOMAIN endpoint
3. Analyze the structure of the response
4. Output a summary of fields and their types
"""
import os
import sys
import json
import requests
import time
import pprint
from collections import defaultdict
from dotenv import load_dotenv
import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analyze_domain')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_domain_data(limit=50):
    """
    Fetch data from MXDOMAIN endpoint.

    Args:
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API with detailed domain data
    """
    # Try different API endpoint formats
    endpoints = [
        f"{BASE_URL}/api/os/mxapidomain",  # Standard REST API format
        f"{BASE_URL}/oslc/os/mxapidomain",  # OSLC format
        f"{BASE_URL}/api/os/MXAPIDOMAIN"   # Uppercase format
    ]

    # Prepare query parameters - try different formats with more fields
    query_params_options = [
        {
            "lean": "0",  # Get full response
            "oslc.pageSize": str(limit),
            "oslc.select": "*"  # Request all fields
        },
        {
            "lean": "0",  # Get full response
            "oslc.pageSize": str(limit),
            "oslc.select": "domainid,value,description,spi:domainid,spi:value,spi:description"
        },
        {
            "_maxItems": str(limit),
            "oslc.select": "*"  # Request all fields
        }
    ]

    # Get username from environment if available
    username = os.getenv('MAXIMO_USERNAME', '')

    # Try different authentication header formats
    header_options = [
        {
            "Accept": "application/json",
            "apikey": API_KEY  # This worked in previous run
        },
        {
            "Accept": "application/json",
            "mxapiapikey": API_KEY
        },
        {
            "Accept": "application/json",
            "maxauth": API_KEY
        },
        {
            "Accept": "application/json",
            "mmxapiapikey": API_KEY
        }
    ]

    # Add user context to all header options if available
    if username:
        for header in header_options:
            header["x-user-context"] = username

    # Try each combination of endpoint, query params, and headers
    for endpoint in endpoints:
        for query_params in query_params_options:
            for headers in header_options:
                logger.info(f"Trying endpoint: {endpoint}")
                logger.info(f"Using headers: {json.dumps(headers, indent=2)}")
                logger.info(f"Using query parameters: {json.dumps(query_params, indent=2)}")

                try:
                    # Make the API request
                    response = requests.get(
                        endpoint,
                        params=query_params,
                        headers=headers,
                        timeout=(3.05, 15)  # Connection timeout, read timeout
                    )

                    # Check for successful response
                    if response.status_code == 200:
                        logger.info(f"Successfully fetched domain data. Status code: {response.status_code}")

                        # Save the raw response for debugging
                        with open('domain_raw_response.json', 'w') as f:
                            f.write(response.text)

                        # Parse the JSON response
                        try:
                            data = response.json()

                            # Check for member key
                            if 'member' in data:
                                logger.info(f"Found {len(data['member'])} domain records")
                                return data
                            elif 'rdfs:member' in data:
                                logger.info(f"Found {len(data['rdfs:member'])} domain records")
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
                        logger.warning(f"Error fetching domain data. Status code: {response.status_code}")
                        logger.warning(f"Response: {response.text[:500]}")
                        continue

                except Exception as e:
                    logger.warning(f"Exception during request: {str(e)}")
                    continue

    logger.error("All endpoints failed")
    return None

def analyze_field_types(data):
    """
    Analyze the structure and field types in the response.

    Args:
        data (dict): JSON response from the API

    Returns:
        dict: Summary of fields and their types
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to analyze")
        return None

    # Initialize field type tracking
    field_types = {}
    field_examples = {}
    field_null_count = defaultdict(int)
    field_presence = defaultdict(int)
    total_records = len(data['member'])

    # Track original to normalized field mapping
    field_mapping = {}

    # Analyze each record
    for record in data['member']:
        # Normalize field names (remove prefixes)
        normalized_record = {}
        for field, value in record.items():
            # Skip internal fields that start with underscore
            if field.startswith('_') and field != '_rowstamp':
                continue

            # Remove common prefixes like 'spi:' or 'rdf:'
            normalized_field = field
            for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                if field.startswith(prefix):
                    normalized_field = field[len(prefix):]
                    field_mapping[normalized_field] = field
                    break

            normalized_record[normalized_field] = value

        # Now analyze the normalized record
        for field, value in normalized_record.items():
            # Track field presence
            field_presence[field] += 1

            # Track null values
            if value is None:
                field_null_count[field] += 1
                continue

            # Determine field type
            value_type = type(value).__name__

            # For the first occurrence of a field, record its type
            if field not in field_types:
                field_types[field] = value_type
                field_examples[field] = value
            # If we see a different type, note the conflict
            elif field_types[field] != value_type:
                field_types[field] = f"{field_types[field]}/{value_type}"

    # Create a summary
    field_summary = {}
    for field in field_types:
        original_field = field_mapping.get(field, field)
        field_summary[field] = {
            'type': field_types[field],
            'example': field_examples.get(field, None),
            'null_count': field_null_count[field],
            'presence_percentage': (field_presence[field] / total_records) * 100,
            'is_required': field_presence[field] == total_records and field_null_count[field] == 0,
            'original_field': original_field
        }

    return field_summary

def suggest_primary_key(data, field_summary):
    """
    Suggest potential primary key fields based on uniqueness.

    Args:
        data (dict): JSON response from the API
        field_summary (dict): Summary of fields and their types

    Returns:
        list: Potential primary key fields
    """
    if not data or 'member' not in data or not data['member']:
        return []

    # Check uniqueness of each field
    unique_values = {}
    total_records = len(data['member'])

    # Prioritize these fields as potential primary keys if they exist and are unique
    priority_fields = ['domainid', 'value', 'id']

    # First pass: check if any priority fields are unique
    for priority_field in priority_fields:
        if priority_field in field_summary:
            # Skip fields that are sometimes null
            if field_summary[priority_field]['null_count'] > 0:
                continue

            # Skip fields that aren't present in all records
            if field_summary[priority_field]['presence_percentage'] < 100:
                continue

            # Get the original field name if it was normalized
            original_field = field_summary[priority_field].get('original_field', priority_field)

            # Collect all values for this field
            values = []
            for record in data['member']:
                # Try both normalized and original field names
                if priority_field in record:
                    values.append(record.get(priority_field))
                elif original_field in record:
                    values.append(record.get(original_field))

            unique_count = len(set(values))

            # If all values are unique, this could be a primary key
            if unique_count == total_records:
                unique_values[priority_field] = unique_count

    # If we found a priority field that's unique, return it
    if unique_values:
        return list(unique_values.keys())

    # Second pass: check all fields
    for field in field_summary:
        # Skip fields that are sometimes null
        if field_summary[field]['null_count'] > 0:
            continue

        # Skip fields that aren't present in all records
        if field_summary[field]['presence_percentage'] < 100:
            continue

        # Get the original field name if it was normalized
        original_field = field_summary[field].get('original_field', field)

        # Collect all values for this field
        values = []
        for record in data['member']:
            # Try both normalized and original field names
            if field in record:
                values.append(record.get(field))
            elif original_field in record:
                values.append(record.get(original_field))

        unique_count = len(set(values))

        # If all values are unique, this could be a primary key
        if unique_count == total_records:
            unique_values[field] = unique_count

    # Sort potential keys by name (prefer shorter names like 'id')
    potential_keys = sorted(unique_values.keys(), key=len)

    return potential_keys

def suggest_sqlite_schema(field_summary, primary_keys):
    """
    Suggest a SQLite schema based on the field analysis.

    Args:
        field_summary (dict): Summary of fields and their types
        primary_keys (list): Potential primary key fields

    Returns:
        str: SQLite CREATE TABLE statement
    """
    # Map Python types to SQLite types
    type_mapping = {
        'str': 'TEXT',
        'int': 'INTEGER',
        'float': 'REAL',
        'bool': 'INTEGER',  # SQLite doesn't have a boolean type
        'dict': 'TEXT',  # Store JSON as text
        'list': 'TEXT',  # Store JSON as text
    }

    # Start building the CREATE TABLE statement
    table_name = 'domains'
    create_table = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"

    # Track fields to include
    included_fields = []

    # First add primary key fields
    if primary_keys:
        for primary_key in primary_keys:
            info = field_summary[primary_key]
            field_type = info['type'].split('/')[0]  # Use first type if multiple
            sqlite_type = type_mapping.get(field_type, 'TEXT')

            create_table += f"    {primary_key} {sqlite_type} NOT NULL,\n"
            included_fields.append(primary_key)

    # Add other fields
    for field, info in field_summary.items():
        # Skip fields we've already added
        if field in included_fields:
            continue

        # Skip internal fields and href fields
        if field.startswith('_') or field == 'href' or field == 'about':
            continue

        # Determine SQLite type
        field_type = info['type'].split('/')[0]  # Use first type if multiple
        sqlite_type = type_mapping.get(field_type, 'TEXT')

        # Add NOT NULL constraint if field is required
        not_null = "NOT NULL" if info['is_required'] else ""

        # Add field definition
        create_table += f"    {field} {sqlite_type} {not_null},\n"
        included_fields.append(field)

    # Add metadata fields for sync tracking
    create_table += "    _rowstamp TEXT,\n"
    create_table += "    _last_sync TIMESTAMP,\n"
    create_table += "    _sync_status TEXT,\n"

    # Add primary key constraint
    if len(primary_keys) > 0:
        create_table += f"    PRIMARY KEY ({', '.join(primary_keys)})\n"
    else:
        # Remove trailing comma from last field
        create_table = create_table.rstrip(',\n') + "\n"

    create_table += ");"

    # Add index creation statements
    indexes = []

    # Add indexes for common query fields
    common_query_fields = ['domainid', 'value']
    for field in common_query_fields:
        if field in field_summary and field not in primary_keys:
            indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{field} ON {table_name}({field});")

    # Add the indexes to the schema
    if indexes:
        create_table += "\n\n-- Indexes\n"
        create_table += "\n".join(indexes)

    return create_table

def main():
    """Main function to fetch and analyze domain data."""
    # Fetch domain data
    domain_data = fetch_domain_data(limit=50)  # Fetch up to 50 records for better analysis

    if not domain_data:
        logger.error("Failed to fetch domain data")
        return

    # Save raw data for reference
    with open('domain_data.json', 'w') as f:
        json.dump(domain_data, f, indent=2)

    logger.info(f"Fetched {len(domain_data.get('member', []))} domain records")

    # Analyze field types
    field_summary = analyze_field_types(domain_data)

    if not field_summary:
        logger.error("Failed to analyze field types")
        return

    # Suggest primary keys
    potential_keys = suggest_primary_key(domain_data, field_summary)

    # Print analysis results
    print("\n=== DOMAIN ENDPOINT ANALYSIS ===\n")
    print(f"Total records analyzed: {len(domain_data.get('member', []))}")
    print(f"Total fields found: {len(field_summary)}")
    print(f"Potential primary keys: {', '.join(potential_keys) or 'None found'}")

    print("\n=== FIELD SUMMARY ===\n")
    for field, info in sorted(field_summary.items()):
        print(f"Field: {field}")
        print(f"  Type: {info['type']}")
        print(f"  Example: {info['example']}")
        print(f"  Null count: {info['null_count']}")
        print(f"  Presence: {info['presence_percentage']:.1f}%")
        print(f"  Required: {info['is_required']}")
        print()

    # Suggest SQLite schema
    sqlite_schema = suggest_sqlite_schema(field_summary, potential_keys)

    print("\n=== SUGGESTED SQLITE SCHEMA ===\n")
    print(sqlite_schema)

    # Save schema to file
    with open('domain_schema.sql', 'w') as f:
        f.write(sqlite_schema)

    logger.info("Analysis complete. Results saved to domain_data.json and domain_schema.sql")

if __name__ == "__main__":
    main()
