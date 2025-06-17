#!/usr/bin/env python3
"""
Script to analyze the MXAPIWODETAIL endpoint structure.
This script will:
1. Load API key from .env file
2. Fetch data from MXAPIWODETAIL endpoint
3. Analyze the structure of the response
4. Output a summary of fields and their types
5. Generate a suggested SQLite schema
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
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analyze_wodetail')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_wodetail_data(site=None, limit=50):
    """
    Fetch data from MXAPIWODETAIL endpoint.

    Args:
        site (str): Site ID to filter by
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API with detailed work order data
    """
    endpoint = f"{BASE_URL}/api/os/mxapiwodetail"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*"  # Request all fields
    }

    # Use a simpler approach with just the site filter
    # OSLC query syntax is very specific and can be tricky

    # Just filter by site if provided
    if site:
        query_params["oslc.where"] = f"siteid=\"{site}\""

    # We'll filter out CAN and CLOSE status work orders in post-processing

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
        logger.info(f"Fetching work order data from {endpoint}")
        logger.info(f"Query parameters: {json.dumps(query_params, indent=2)}")

        response = requests.get(
            endpoint,
            params=query_params,
            headers=headers,
            timeout=(3.05, 15)  # Connection timeout, read timeout
        )

        # Check for successful response
        if response.status_code == 200:
            logger.info(f"Successfully fetched work order data. Status code: {response.status_code}")

            # Save the raw response for debugging
            with open('wodetail_raw_response.json', 'w') as f:
                f.write(response.text)

            # Parse the JSON response
            try:
                data = response.json()

                # Check for member key
                if 'member' in data:
                    logger.info(f"Found {len(data['member'])} work order records")
                    return data
                elif 'rdfs:member' in data:
                    logger.info(f"Found {len(data['rdfs:member'])} work order records")
                    # Standardize the data structure
                    data['member'] = data['rdfs:member']
                    return data
                else:
                    logger.warning(f"No member data found in response. Keys: {list(data.keys())}")
                    return None

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.warning(f"Response text: {response.text[:500]}")
                return None
        else:
            logger.warning(f"Error fetching work order data. Status code: {response.status_code}")
            logger.warning(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        logger.warning(f"Exception during request: {str(e)}")
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

def analyze_nested_structures(data):
    """
    Analyze nested structures in the response to identify related tables.

    Args:
        data (dict): JSON response from the API

    Returns:
        dict: Summary of nested structures and their fields
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to analyze")
        return None

    # Initialize nested structure tracking
    nested_structures = {}

    # Analyze each record
    for record in data['member']:
        # Look for nested structures (lists or dicts)
        for field, value in record.items():
            # Skip non-nested fields
            if not isinstance(value, (list, dict)):
                continue

            # Remove common prefixes
            normalized_field = field
            for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                if field.startswith(prefix):
                    normalized_field = field[len(prefix):]
                    break

            # If it's a list, analyze the first item
            if isinstance(value, list) and value:
                # Skip empty lists
                if not value:
                    continue

                # Initialize structure if not seen before
                if normalized_field not in nested_structures:
                    nested_structures[normalized_field] = {
                        'type': 'list',
                        'fields': {},
                        'example_count': len(value)
                    }

                # Analyze the first item in the list
                first_item = value[0]
                if isinstance(first_item, dict):
                    for item_field, item_value in first_item.items():
                        # Normalize field name
                        normalized_item_field = item_field
                        for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                            if item_field.startswith(prefix):
                                normalized_item_field = item_field[len(prefix):]
                                break

                        # Record field type
                        field_type = type(item_value).__name__
                        if normalized_item_field not in nested_structures[normalized_field]['fields']:
                            nested_structures[normalized_field]['fields'][normalized_item_field] = {
                                'type': field_type,
                                'example': item_value
                            }

            # If it's a dict, analyze its fields
            elif isinstance(value, dict):
                # Initialize structure if not seen before
                if normalized_field not in nested_structures:
                    nested_structures[normalized_field] = {
                        'type': 'dict',
                        'fields': {}
                    }

                # Analyze each field in the dict
                for dict_field, dict_value in value.items():
                    # Normalize field name
                    normalized_dict_field = dict_field
                    for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                        if dict_field.startswith(prefix):
                            normalized_dict_field = dict_field[len(prefix):]
                            break

                    # Record field type
                    field_type = type(dict_value).__name__
                    if normalized_dict_field not in nested_structures[normalized_field]['fields']:
                        nested_structures[normalized_field]['fields'][normalized_dict_field] = {
                            'type': field_type,
                            'example': dict_value
                        }

    return nested_structures

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
    priority_fields = ['wonum', 'workorderid']

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

def suggest_sqlite_schema(field_summary, nested_structures, primary_keys):
    """
    Suggest a SQLite schema based on the field analysis.

    Args:
        field_summary (dict): Summary of fields and their types
        nested_structures (dict): Summary of nested structures
        primary_keys (list): Potential primary key fields

    Returns:
        str: SQLite CREATE TABLE statements
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

    # Start building the CREATE TABLE statements
    schema = ""

    # Main workorder table
    schema += "-- Main workorder table\n"
    schema += "CREATE TABLE IF NOT EXISTS workorder (\n"

    # Track fields to include
    included_fields = []

    # First add primary key fields
    if primary_keys:
        for primary_key in primary_keys:
            info = field_summary[primary_key]
            field_type = info['type'].split('/')[0]  # Use first type if multiple
            sqlite_type = type_mapping.get(field_type, 'TEXT')

            schema += f"    {primary_key} {sqlite_type} NOT NULL,\n"
            included_fields.append(primary_key)

    # Add other fields
    for field, info in field_summary.items():
        # Skip fields we've already added
        if field in included_fields:
            continue

        # Skip internal fields and href fields
        if field.startswith('_') or field == 'href' or field == 'about':
            continue

        # Skip nested structures (we'll create separate tables for these)
        if field in nested_structures:
            continue

        # Determine SQLite type
        field_type = info['type'].split('/')[0]  # Use first type if multiple
        sqlite_type = type_mapping.get(field_type, 'TEXT')

        # Add NOT NULL constraint if field is required
        not_null = "NOT NULL" if info['is_required'] else ""

        # Add field definition
        schema += f"    {field} {sqlite_type} {not_null},\n"
        included_fields.append(field)

    # Add metadata fields for sync tracking
    schema += "    _rowstamp TEXT,\n"
    schema += "    _last_sync TIMESTAMP,\n"
    schema += "    _sync_status TEXT,\n"

    # Add primary key constraint
    if len(primary_keys) > 0:
        schema += f"    PRIMARY KEY ({', '.join(primary_keys)})\n"
    else:
        # Remove trailing comma from last field
        schema = schema.rstrip(',\n') + "\n"

    schema += ");\n\n"

    # Add index creation statements for main table
    schema += "-- Indexes for workorder table\n"

    # Add indexes for common query fields
    common_query_fields = ['siteid', 'status', 'wonum', 'workorderid', 'location', 'assetnum']
    for field in common_query_fields:
        if field in field_summary and field not in primary_keys:
            schema += f"CREATE INDEX IF NOT EXISTS idx_workorder_{field} ON workorder({field});\n"

    schema += "\n"

    # Create tables for nested structures
    for nested_field, info in nested_structures.items():
        # Skip if not a list type (we only create tables for list relationships)
        if info['type'] != 'list':
            continue

        # Determine table name (singular form of nested field)
        if nested_field.endswith('s'):
            table_name = nested_field[:-1]  # Remove trailing 's'
        else:
            table_name = f"{nested_field}_item"

        schema += f"-- {nested_field} table\n"
        schema += f"CREATE TABLE IF NOT EXISTS {table_name} (\n"

        # Add ID field as primary key
        schema += f"    {table_name}id INTEGER PRIMARY KEY AUTOINCREMENT,\n"

        # Add foreign key to main table
        for pk in primary_keys:
            field_type = field_summary[pk]['type'].split('/')[0]
            sqlite_type = type_mapping.get(field_type, 'TEXT')
            schema += f"    {pk} {sqlite_type} NOT NULL,\n"

        # Add fields from nested structure
        for field, field_info in info['fields'].items():
            # Skip internal fields and href fields
            if field.startswith('_') or field == 'href' or field == 'about':
                continue

            # Determine SQLite type
            field_type = field_info['type']
            sqlite_type = type_mapping.get(field_type, 'TEXT')

            # Add field definition
            schema += f"    {field} {sqlite_type},\n"

        # Add metadata fields for sync tracking
        schema += "    _rowstamp TEXT,\n"
        schema += "    _last_sync TIMESTAMP,\n"
        schema += "    _sync_status TEXT,\n"

        # Add foreign key constraint
        fk_constraint = ", ".join(primary_keys)
        schema += f"    FOREIGN KEY ({fk_constraint}) REFERENCES workorder({fk_constraint})\n"

        schema += ");\n\n"

        # Add indexes for related table
        schema += f"-- Indexes for {table_name} table\n"

        # Add indexes for foreign key fields
        for pk in primary_keys:
            schema += f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{pk} ON {table_name}({pk});\n"

        schema += "\n"

    return schema

def main():
    """Main function to fetch and analyze work order data."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze MXAPIWODETAIL endpoint')
    parser.add_argument('--site', help='Site ID to filter by')
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of records to fetch')
    args = parser.parse_args()

    # Load the raw response from file if it exists
    try:
        with open('wodetail_raw_response.json', 'r') as f:
            raw_response = f.read()
            wodetail_data = json.loads(raw_response)
            logger.info("Loaded work order data from wodetail_raw_response.json")

            # Check if the data has the expected structure
            if 'rdfs:member' in wodetail_data:
                wodetail_data['member'] = wodetail_data['rdfs:member']
                logger.info(f"Found {len(wodetail_data['member'])} work order records")
            elif 'member' in wodetail_data:
                logger.info(f"Found {len(wodetail_data['member'])} work order records")
            else:
                logger.warning("Loaded data does not have the expected structure")
                wodetail_data = None
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("No valid cached data found, fetching from API")
        wodetail_data = fetch_wodetail_data(args.site, args.limit)

    if not wodetail_data:
        logger.error("Failed to fetch or load work order data")
        return

    # Save raw data for reference
    with open('wodetail_data.json', 'w') as f:
        json.dump(wodetail_data, f, indent=2)

    logger.info(f"Processing {len(wodetail_data.get('member', []))} work order records")

    # Analyze field types
    field_summary = analyze_field_types(wodetail_data)

    if not field_summary:
        logger.error("Failed to analyze field types")
        return

    # Analyze nested structures
    nested_structures = analyze_nested_structures(wodetail_data)

    if not nested_structures:
        logger.warning("No nested structures found")

    # Suggest primary keys
    potential_keys = suggest_primary_key(wodetail_data, field_summary)

    # Print analysis results
    print("\n=== WORK ORDER ENDPOINT ANALYSIS ===\n")
    print(f"Total records analyzed: {len(wodetail_data.get('member', []))}")
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

    if nested_structures:
        print("\n=== NESTED STRUCTURES ===\n")
        for field, info in sorted(nested_structures.items()):
            print(f"Structure: {field}")
            print(f"  Type: {info['type']}")
            if info['type'] == 'list':
                print(f"  Example count: {info.get('example_count', 0)}")
            print(f"  Fields: {len(info['fields'])}")
            for subfield, subinfo in sorted(info['fields'].items()):
                print(f"    {subfield}: {subinfo['type']} (Example: {subinfo['example']})")
            print()

    # Suggest SQLite schema
    sqlite_schema = suggest_sqlite_schema(field_summary, nested_structures, potential_keys)

    print("\n=== SUGGESTED SQLITE SCHEMA ===\n")
    print(sqlite_schema)

    # Save schema to file
    with open('wodetail_schema.sql', 'w') as f:
        f.write(sqlite_schema)

    logger.info("Analysis complete. Results saved to wodetail_data.json and wodetail_schema.sql")

if __name__ == "__main__":
    main()
