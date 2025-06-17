#!/usr/bin/env python3
"""
Script to analyze the MXAPIINVENTORY endpoint structure.
This script will:
1. Load API key from .env file
2. Fetch data from MXAPIINVENTORY endpoint with status="ACTIVE"
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
logger = logging.getLogger('analyze_inventory')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_inventory_data(site=None, limit=50):
    """
    Fetch data from MXAPIINVENTORY endpoint with status="ACTIVE".
    
    Args:
        site (str): Site ID to filter by
        limit (int): Maximum number of records to fetch
        
    Returns:
        dict: JSON response from the API with detailed inventory data
    """
    # Try different API endpoint formats
    endpoints = [
        f"{BASE_URL}/api/os/mxapiinventory",  # Standard REST API format
        f"{BASE_URL}/oslc/os/mxapiinventory",  # OSLC format
        f"{BASE_URL}/api/os/MXAPIINVENTORY"   # Uppercase format
    ]
    
    # Prepare query parameters
    query_params_options = [
        {
            "lean": "0",  # Get full response
            "oslc.pageSize": str(limit),
            "oslc.select": "*",  # Request all fields
            "oslc.where": "status=\"ACTIVE\""  # Filter for active inventory
        },
        {
            "lean": "0",  # Get full response
            "oslc.pageSize": str(limit),
            "oslc.select": "*",
            "oslc.where": "spi:status=\"ACTIVE\""  # Alternative filter syntax
        },
        {
            "_maxItems": str(limit),
            "oslc.select": "*",  # Request all fields
            "oslc.where": "status=\"ACTIVE\""  # Filter for active inventory
        }
    ]
    
    # Add site filter if provided
    if site:
        for params in query_params_options:
            if "oslc.where" in params:
                if params["oslc.where"].startswith("status="):
                    params["oslc.where"] += f" and siteid=\"{site}\""
                elif params["oslc.where"].startswith("spi:status="):
                    params["oslc.where"] += f" and spi:siteid=\"{site}\""
    
    # Get username from environment if available
    username = os.getenv('MAXIMO_USERNAME', '')
    
    # Try different authentication header formats
    header_options = [
        {
            "Accept": "application/json",
            "apikey": API_KEY  # This worked in previous runs
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
    
    # Try each endpoint with each query parameter option and header option
    for endpoint in endpoints:
        for query_params in query_params_options:
            for headers in header_options:
                logger.info(f"Trying endpoint: {endpoint}")
                logger.info(f"With query parameters: {json.dumps(query_params, indent=2)}")
                logger.info(f"With headers: {json.dumps(headers, indent=2)}")
                
                try:
                    # Make the API request
                    response = requests.get(
                        endpoint,
                        params=query_params,
                        headers=headers,
                        timeout=(3.05, 30)  # Connection timeout, read timeout
                    )
                    
                    # Check if the request was successful
                    if response.status_code == 200:
                        logger.info(f"Request successful: {response.status_code}")
                        
                        # Try to parse the JSON response
                        try:
                            data = response.json()
                            
                            # Check if we have data
                            if data:
                                logger.info("Successfully parsed JSON response")
                                
                                # Look for member data in different possible formats
                                if 'member' in data:
                                    logger.info(f"Found {len(data['member'])} inventory records in 'member' key")
                                    return data
                                elif 'rdfs:member' in data:
                                    logger.info(f"Found {len(data['rdfs:member'])} inventory records in 'rdfs:member' key")
                                    data['member'] = data['rdfs:member']
                                    return data
                                elif 'spi:member' in data:
                                    logger.info(f"Found {len(data['spi:member'])} inventory records in 'spi:member' key")
                                    data['member'] = data['spi:member']
                                    return data
                                else:
                                    logger.warning("Response does not contain 'member' key")
                                    logger.debug(f"Response keys: {list(data.keys())}")
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse JSON response")
                    else:
                        logger.warning(f"Request failed with status code: {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request exception: {str(e)}")
    
    logger.error("All endpoint attempts failed")
    return None

def analyze_field_types(data):
    """
    Analyze the field types in the inventory data.
    
    Args:
        data (dict): JSON response from the API
        
    Returns:
        dict: Summary of field types, examples, and presence
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to analyze")
        return None
    
    # Get the first record for initial analysis
    first_record = data['member'][0]
    
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
        # Create a normalized version of the record (remove prefixes)
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
                # Keep the non-null example
                if field_examples[field] is None and value is not None:
                    field_examples[field] = value
    
    # Create a summary of the field analysis
    field_summary = {}
    for field in field_types.keys():
        presence_pct = (field_presence[field] / total_records) * 100
        is_required = presence_pct == 100 and field_null_count[field] == 0
        
        field_summary[field] = {
            'type': field_types[field],
            'example': field_examples[field],
            'null_count': field_null_count[field],
            'presence_count': field_presence[field],
            'presence_percentage': presence_pct,
            'is_required': is_required,
            'original_field': field_mapping.get(field, field)
        }
    
    return field_summary

def analyze_nested_structures(data):
    """
    Analyze nested structures in the inventory data.
    
    Args:
        data (dict): JSON response from the API
        
    Returns:
        dict: Summary of nested structures
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to analyze")
        return None
    
    nested_structures = {}
    
    # Look for nested structures in the first few records
    for record in data['member'][:5]:
        for field, value in record.items():
            # Skip non-dict and non-list fields
            if not isinstance(value, (dict, list)):
                continue
            
            # Remove common prefixes
            normalized_field = field
            for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                if field.startswith(prefix):
                    normalized_field = field[len(prefix):]
                    break
            
            # Process dict fields
            if isinstance(value, dict) and value:
                if normalized_field not in nested_structures:
                    nested_structures[normalized_field] = {
                        'type': 'dict',
                        'fields': {}
                    }
                
                # Analyze the fields in this dict
                for subfield, subvalue in value.items():
                    if subfield not in nested_structures[normalized_field]['fields']:
                        nested_structures[normalized_field]['fields'][subfield] = {
                            'type': type(subvalue).__name__,
                            'example': subvalue
                        }
            
            # Process list fields
            elif isinstance(value, list) and value:
                if normalized_field not in nested_structures:
                    nested_structures[normalized_field] = {
                        'type': 'list',
                        'example_count': len(value),
                        'fields': {}
                    }
                
                # If the list contains dicts, analyze the first item
                if value and isinstance(value[0], dict):
                    for subfield, subvalue in value[0].items():
                        if subfield not in nested_structures[normalized_field]['fields']:
                            nested_structures[normalized_field]['fields'][subfield] = {
                                'type': type(subvalue).__name__,
                                'example': subvalue
                            }
    
    return nested_structures

def suggest_primary_key(data, field_summary):
    """
    Suggest potential primary key fields based on uniqueness.
    
    Args:
        data (dict): JSON response from the API
        field_summary (dict): Summary of field types and presence
        
    Returns:
        list: Potential primary key fields
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to analyze")
        return []
    
    # Look for fields that might be unique identifiers
    potential_keys = []
    
    # Common primary key field names
    common_key_fields = [
        'itemnum', 'inventoryid', 'invid', 'itemid', 'id', 'inventorynum'
    ]
    
    # Check for common combinations that might form a composite key
    composite_keys = [
        ['itemnum', 'siteid'],
        ['itemnum', 'siteid', 'location'],
        ['itemnum', 'location'],
        ['itemnum', 'storeloc']
    ]
    
    # Check each common key field
    for key_field in common_key_fields:
        if key_field in field_summary and field_summary[key_field]['is_required']:
            # Check if this field is unique
            values = set()
            for record in data['member']:
                # Get the normalized field name
                norm_field = key_field
                if key_field not in record:
                    for field in record:
                        if field.endswith(':' + key_field):
                            norm_field = field
                            break
                
                if norm_field in record:
                    values.add(str(record[norm_field]))
            
            if len(values) == len(data['member']):
                potential_keys.append(key_field)
    
    # Check composite keys
    for composite_key in composite_keys:
        # Check if all fields in the composite key exist
        if all(field in field_summary for field in composite_key):
            # Check if the combination is unique
            values = set()
            for record in data['member']:
                # Create a composite value
                composite_value = []
                for field in composite_key:
                    # Get the normalized field name
                    norm_field = field
                    if field not in record:
                        for rec_field in record:
                            if rec_field.endswith(':' + field):
                                norm_field = rec_field
                                break
                    
                    if norm_field in record:
                        composite_value.append(str(record[norm_field]))
                    else:
                        composite_value.append('NULL')
                
                values.add(tuple(composite_value))
            
            if len(values) == len(data['member']):
                potential_keys.append(' + '.join(composite_key))
    
    return potential_keys

def suggest_sqlite_schema(field_summary, nested_structures=None, potential_keys=None):
    """
    Suggest a SQLite schema based on the field analysis.
    
    Args:
        field_summary (dict): Summary of field types and presence
        nested_structures (dict): Summary of nested structures
        potential_keys (list): Potential primary key fields
        
    Returns:
        str: Suggested SQLite schema
    """
    if not field_summary:
        logger.error("No field summary to generate schema")
        return None
    
    # Determine the table name
    table_name = "inventory"
    
    # Start building the CREATE TABLE statement
    create_table = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    
    # Track fields that will be part of the primary key
    primary_keys = []
    
    # Process potential primary keys
    if potential_keys:
        # Use the first potential key (could be composite)
        primary_key = potential_keys[0]
        
        # If it's a composite key, split it
        if ' + ' in primary_key:
            primary_keys = primary_key.split(' + ')
        else:
            primary_keys = [primary_key]
    
    # If no primary key was found, use a reasonable default
    if not primary_keys:
        # For inventory, a common primary key is (itemnum, siteid, location)
        if all(field in field_summary for field in ['itemnum', 'siteid', 'location']):
            primary_keys = ['itemnum', 'siteid', 'location']
        # Fallback to just itemnum and siteid
        elif all(field in field_summary for field in ['itemnum', 'siteid']):
            primary_keys = ['itemnum', 'siteid']
    
    # Add fields to the schema
    for field, info in sorted(field_summary.items()):
        # Skip fields that are nested structures
        if nested_structures and field in nested_structures:
            continue
        
        # Determine the SQLite type based on the field type
        field_type = info['type']
        sqlite_type = "TEXT"  # Default to TEXT
        
        if field_type == 'int':
            sqlite_type = "INTEGER"
        elif field_type == 'float':
            sqlite_type = "REAL"
        elif field_type == 'bool':
            sqlite_type = "INTEGER"  # SQLite doesn't have a boolean type
        elif field_type in ['dict', 'list']:
            continue  # Skip complex types
        
        # Determine if the field is required
        is_required = info['is_required']
        not_null = "NOT NULL" if is_required and field in primary_keys else ""
        
        # Add the field to the schema
        create_table += f"    {field} {sqlite_type} {not_null},\n"
    
    # Add _rowstamp field
    create_table += "    _rowstamp TEXT,\n"
    
    # Add metadata fields for sync tracking
    create_table += "    _last_sync TIMESTAMP,\n"
    create_table += "    _sync_status TEXT,\n"
    
    # Add primary key constraint
    if primary_keys:
        create_table += f"    PRIMARY KEY ({', '.join(primary_keys)})\n"
    else:
        # Remove trailing comma
        create_table = create_table.rstrip(',\n') + "\n"
    
    create_table += ");"
    
    # Add index creation statements
    indexes = []
    
    # Add indexes for common query fields
    common_query_fields = ['status', 'siteid', 'location', 'itemnum', 'storeloc']
    for field in common_query_fields:
        if field in field_summary and field not in primary_keys:
            indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{field} ON {table_name}({field});")
    
    # Add the indexes to the schema
    if indexes:
        create_table += "\n\n-- Indexes\n"
        create_table += "\n".join(indexes)
    
    # If we have nested structures, create additional tables
    if nested_structures:
        for struct_name, struct_info in nested_structures.items():
            if struct_info['type'] == 'list' and struct_info['fields']:
                # Create a related table for this list
                related_table = f"{table_name}_{struct_name.lower()}"
                create_table += f"\n\n-- Related table for {struct_name}\n"
                create_table += f"CREATE TABLE IF NOT EXISTS {related_table} (\n"
                create_table += f"    {related_table}id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                
                # Add foreign key fields
                for pk in primary_keys:
                    if pk in field_summary:
                        field_type = field_summary[pk]['type']
                        sqlite_type = "TEXT"  # Default to TEXT
                        
                        if field_type == 'int':
                            sqlite_type = "INTEGER"
                        elif field_type == 'float':
                            sqlite_type = "REAL"
                        
                        create_table += f"    {pk} {sqlite_type} NOT NULL,\n"
                
                # Add fields from the nested structure
                for subfield, subinfo in struct_info['fields'].items():
                    subfield_type = subinfo['type']
                    sqlite_type = "TEXT"  # Default to TEXT
                    
                    if subfield_type == 'int':
                        sqlite_type = "INTEGER"
                    elif subfield_type == 'float':
                        sqlite_type = "REAL"
                    elif subfield_type == 'bool':
                        sqlite_type = "INTEGER"
                    elif subfield_type in ['dict', 'list']:
                        continue  # Skip complex types
                    
                    create_table += f"    {subfield} {sqlite_type},\n"
                
                # Add metadata fields
                create_table += "    _rowstamp TEXT,\n"
                create_table += "    _last_sync TIMESTAMP,\n"
                create_table += "    _sync_status TEXT,\n"
                
                # Add foreign key constraint
                if primary_keys:
                    fk_fields = ', '.join(primary_keys)
                    create_table += f"    FOREIGN KEY ({fk_fields}) REFERENCES {table_name}({fk_fields})\n"
                else:
                    # Remove trailing comma
                    create_table = create_table.rstrip(',\n') + "\n"
                
                create_table += ");"
                
                # Add indexes for the related table
                related_indexes = []
                for pk in primary_keys:
                    related_indexes.append(f"CREATE INDEX IF NOT EXISTS idx_{related_table}_{pk} ON {related_table}({pk});")
                
                if related_indexes:
                    create_table += "\n\n-- Indexes for related table\n"
                    create_table += "\n".join(related_indexes)
    
    return create_table

def main():
    """Main function to fetch and analyze inventory data."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze MXAPIINVENTORY endpoint structure')
    parser.add_argument('--site', type=str, help='Site ID to filter by')
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of records to fetch')
    parser.add_argument('--load-file', type=str, help='Load data from file instead of API')
    args = parser.parse_args()
    
    # Try to load data from file if specified
    inventory_data = None
    if args.load_file:
        try:
            with open(args.load_file, 'r') as f:
                inventory_data = json.load(f)
                logger.info(f"Loaded data from {args.load_file}")
                
                # Check if the data has the expected structure
                if 'rdfs:member' in inventory_data:
                    inventory_data['member'] = inventory_data['rdfs:member']
                    logger.info(f"Found {len(inventory_data['member'])} inventory records")
                elif 'member' in inventory_data:
                    logger.info(f"Found {len(inventory_data['member'])} inventory records")
                else:
                    logger.warning("Loaded data does not have the expected structure")
                    inventory_data = None
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No valid cached data found, fetching from API")
            inventory_data = fetch_inventory_data(args.site, args.limit)
    else:
        # Fetch inventory data
        inventory_data = fetch_inventory_data(args.site, args.limit)
    
    if not inventory_data:
        logger.error("Failed to fetch or load inventory data")
        return
    
    # Save raw data for reference
    with open('inventory_data.json', 'w') as f:
        json.dump(inventory_data, f, indent=2)
    
    logger.info(f"Fetched {len(inventory_data.get('member', []))} inventory records")
    
    # Analyze field types
    field_summary = analyze_field_types(inventory_data)
    
    if not field_summary:
        logger.error("Failed to analyze field types")
        return
    
    # Analyze nested structures
    nested_structures = analyze_nested_structures(inventory_data)
    
    if not nested_structures:
        logger.warning("No nested structures found")
    
    # Suggest primary keys
    potential_keys = suggest_primary_key(inventory_data, field_summary)
    
    # Print analysis results
    print("\n=== INVENTORY ENDPOINT ANALYSIS ===\n")
    print(f"Total records analyzed: {len(inventory_data.get('member', []))}")
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
    with open('inventory_schema.sql', 'w') as f:
        f.write(sqlite_schema)
    
    logger.info("Analysis complete. Results saved to inventory_data.json and inventory_schema.sql")

if __name__ == "__main__":
    main()
