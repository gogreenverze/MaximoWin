#!/usr/bin/env python3
"""
Script to synchronize work order data from MXAPIWODETAIL endpoint to local SQLite database.
This script will:
1. Load API key from .env file
2. Fetch data from MXAPIWODETAIL endpoint
3. Process and normalize the data
4. Sync the data to the local SQLite database
"""
import os
import sys
import json
import requests
import time
import datetime
import sqlite3
import logging
import argparse
from collections import defaultdict
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sync_wodetail')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

def get_last_sync_time(db_path, endpoint="MXAPIWODETAIL"):
    """
    Get the last sync time for the specified endpoint.

    Args:
        db_path (str): Path to the SQLite database
        endpoint (str): API endpoint name

    Returns:
        str: Last sync time in ISO format, or None if no previous sync
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT last_sync FROM sync_status WHERE endpoint = ?",
            (endpoint,)
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]

        return None
    except Exception as e:
        logger.error(f"Error getting last sync time: {str(e)}")
        return None

def fetch_wodetail_data(site=None, last_sync=None, limit=100, status=None):
    """
    Fetch work order data from MXAPIWODETAIL endpoint.

    Args:
        site (str): Site ID to filter by
        last_sync (str): Last sync time in ISO format
        limit (int): Maximum number of records to fetch
        status (str): Work order status to filter by

    Returns:
        dict: JSON response from the API
    """
    endpoint = f"{BASE_URL}/api/os/mxapiwodetail"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*"  # Request all fields
    }

    # Build the filter
    # Start with the site filter
    if site:
        base_filter = f"siteid=\"{site}\""
    else:
        base_filter = "siteid=\"LCVIRQ\""

    # Add historyflag=0 filter
    base_filter += " and historyflag=0"

    # Add status filter if provided
    if status:
        base_filter += f" and status=\"{status}\""

    query_params["oslc.where"] = base_filter

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
            timeout=(3.05, 30)  # Connection timeout, read timeout (increased to 30 seconds)
        )

        # Check for successful response
        if response.status_code == 200:
            logger.info(f"Successfully fetched work order data. Status code: {response.status_code}")

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
                    logger.error(f"No member data found in response. Keys: {list(data.keys())}")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text: {response.text[:500]}")
                return None
        else:
            logger.error(f"Error fetching work order data. Status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        logger.error(f"Exception during request: {str(e)}")
        return None

def normalize_record(record):
    """
    Normalize a work order record by removing prefixes and extracting nested data.

    Args:
        record (dict): Raw work order record from API

    Returns:
        dict: Normalized work order record
    """
    # Initialize normalized record
    normalized = {}

    # Process each field
    for field, value in record.items():
        # Skip internal fields that start with underscore (except _rowstamp)
        if field.startswith('_') and field != '_rowstamp':
            continue

        # Remove common prefixes like 'spi:' or 'rdf:'
        normalized_field = field
        for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
            if field.startswith(prefix):
                normalized_field = field[len(prefix):]
                break

        normalized[normalized_field] = value

    return normalized

def extract_workorder_data(record):
    """
    Extract work order data from a normalized record.

    Args:
        record (dict): Normalized work order record

    Returns:
        dict: Work order record for database
    """
    # Define fields to extract
    workorder_fields = [
        'wonum', 'workorderid', 'description', 'status', 'status_description',
        'siteid', 'orgid', 'location', 'assetnum', 'parent', 'woclass',
        'woclass_description', 'worktype', 'wopriority', 'wopriority_description',
        'reportedby', 'reportdate', 'createdby', 'createdate', 'changedate',
        'changeby', 'owner', 'assignedownergroup', 'historyflag', 'istask',
        'taskid', 'estdur', 'estlabhrs', 'estlabcost', 'estmatcost', 'esttoolcost',
        'estservcost', 'esttotalcost', 'actlabhrs', 'actlabcost', 'actmatcost',
        'acttoolcost', 'actservcost', 'acttotalcost', 'haschildren',
        'targstartdate', 'targcompdate', 'actstart', 'actfinish', 'statusdate',
        'wogroup', '_rowstamp'
    ]

    # Check if we have the required fields
    missing_fields = []
    if 'wonum' not in record:
        missing_fields.append('wonum')
    if 'workorderid' not in record:
        missing_fields.append('workorderid')

    if missing_fields:
        logger.warning(f"Record missing required fields: {', '.join(missing_fields)}")
        logger.debug(f"Record keys: {list(record.keys())}")
        return None

    # Create work order record with available fields
    workorder_record = {}
    for field in workorder_fields:
        if field in record:
            workorder_record[field] = record[field]

    # Add sync metadata
    workorder_record['_last_sync'] = datetime.datetime.now().isoformat()
    workorder_record['_sync_status'] = 'synced'

    return workorder_record

def extract_woserviceaddress_data(record, wonum, workorderid):
    """
    Extract work order service address data from a normalized record.

    Args:
        record (dict): Normalized work order service address record
        wonum (str): Work order number
        workorderid (int): Work order ID

    Returns:
        list: List of work order service address records
    """
    if 'woserviceaddress' not in record or not record['woserviceaddress']:
        return []

    address_records = []

    for address in record['woserviceaddress']:
        # Normalize the address record
        norm_address = normalize_record(address)

        # Create address record
        address_record = {
            'woserviceaddressid': norm_address.get('woserviceaddressid'),
            'wonum': wonum,
            'workorderid': workorderid,
            'orgid': norm_address.get('orgid'),
            'addresscode': norm_address.get('addresscode'),
            'description': norm_address.get('description'),
            'addressline1': norm_address.get('addressline1'),
            'addressline2': norm_address.get('addressline2'),
            'addressline3': norm_address.get('addressline3'),
            'city': norm_address.get('city'),
            'country': norm_address.get('country'),
            'county': norm_address.get('county'),
            'stateprovince': norm_address.get('stateprovince'),
            'postalcode': norm_address.get('postalcode'),
            'langcode': norm_address.get('langcode'),
            'hasld': norm_address.get('hasld'),
            'addressischanged': norm_address.get('addressischanged'),
            '_rowstamp': norm_address.get('_rowstamp'),
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        address_records.append(address_record)

    return address_records

def extract_wolabor_data(record, wonum, workorderid):
    """
    Extract work order labor data from a normalized record.

    Args:
        record (dict): Normalized work order record
        wonum (str): Work order number
        workorderid (int): Work order ID

    Returns:
        list: List of work order labor records
    """
    if 'wolabor' not in record or not record['wolabor']:
        return []

    labor_records = []

    for labor in record['wolabor']:
        # Normalize the labor record
        norm_labor = normalize_record(labor)

        # Create labor record
        labor_record = {
            'wolaborid': norm_labor.get('wolaborid'),
            'wonum': wonum,
            'workorderid': workorderid,
            'laborcode': norm_labor.get('laborcode'),
            'laborhrs': norm_labor.get('laborhrs'),
            'startdate': norm_labor.get('startdate'),
            'finishdate': norm_labor.get('finishdate'),
            'transdate': norm_labor.get('transdate'),
            'regularhrs': norm_labor.get('regularhrs'),
            'premiumpayhours': norm_labor.get('premiumpayhours'),
            'labtransid': norm_labor.get('labtransid'),
            '_rowstamp': norm_labor.get('_rowstamp'),
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        labor_records.append(labor_record)

    return labor_records

def extract_womaterial_data(record, wonum, workorderid):
    """
    Extract work order material data from a normalized record.

    Args:
        record (dict): Normalized work order record
        wonum (str): Work order number
        workorderid (int): Work order ID

    Returns:
        list: List of work order material records
    """
    if 'womaterial' not in record or not record['womaterial']:
        return []

    material_records = []

    for material in record['womaterial']:
        # Normalize the material record
        norm_material = normalize_record(material)

        # Create material record
        material_record = {
            'womaterialid': norm_material.get('womaterialid'),
            'wonum': wonum,
            'workorderid': workorderid,
            'itemnum': norm_material.get('itemnum'),
            'itemsetid': norm_material.get('itemsetid'),
            'description': norm_material.get('description'),
            'itemqty': norm_material.get('itemqty'),
            'unitcost': norm_material.get('unitcost'),
            'linecost': norm_material.get('linecost'),
            'storeloc': norm_material.get('storeloc'),
            'siteid': norm_material.get('siteid'),
            'orgid': norm_material.get('orgid'),
            '_rowstamp': norm_material.get('_rowstamp'),
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        material_records.append(material_record)

    return material_records

def extract_wotool_data(record, wonum, workorderid):
    """
    Extract work order tool data from a normalized record.

    Args:
        record (dict): Normalized work order record
        wonum (str): Work order number
        workorderid (int): Work order ID

    Returns:
        list: List of work order tool records
    """
    if 'wotool' not in record or not record['wotool']:
        return []

    tool_records = []

    for tool in record['wotool']:
        # Normalize the tool record
        norm_tool = normalize_record(tool)

        # Create tool record
        tool_record = {
            'wotoolid': norm_tool.get('wotoolid'),
            'wonum': wonum,
            'workorderid': workorderid,
            'toolnum': norm_tool.get('toolnum'),
            'toolhrs': norm_tool.get('toolhrs'),
            'toolrate': norm_tool.get('toolrate'),
            'toolcost': norm_tool.get('toolcost'),
            '_rowstamp': norm_tool.get('_rowstamp'),
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        tool_records.append(tool_record)

    return tool_records

def process_data(data):
    """
    Process and normalize the work order data.

    Args:
        data (dict): Raw data from API

    Returns:
        dict: Processed data with tables and records
    """
    if not data or 'member' not in data:
        logger.error("No data to process")
        return None

    # Initialize processed data structure
    processed_data = {
        'workorder': [],
        'woserviceaddress': [],
        'wolabor': [],
        'womaterial': [],
        'wotool': []
    }

    # Track record processing stats
    stats = {
        'total': len(data['member']),
        'skipped_status': 0,
        'skipped_historyflag': 0,
        'skipped_missing_fields': 0,
        'processed': 0
    }

    # Process each work order record
    for record in data['member']:
        # Skip records with status CAN or CLOSE
        if record.get('spi:status') in ['CAN', 'CLOSE']:
            stats['skipped_status'] += 1
            continue

        # Skip records with historyflag=1
        if record.get('spi:historyflag') == 1:
            stats['skipped_historyflag'] += 1
            continue

        # Normalize the record
        normalized = normalize_record(record)

        # Extract work order record
        workorder_record = extract_workorder_data(normalized)

        if not workorder_record:
            stats['skipped_missing_fields'] += 1
            continue

        # Add to processed data
        processed_data['workorder'].append(workorder_record)
        stats['processed'] += 1

        # Extract related data
        wonum = workorder_record['wonum']
        workorderid = workorder_record['workorderid']

        # Extract service address data
        service_address_records = extract_woserviceaddress_data(normalized, wonum, workorderid)
        processed_data['woserviceaddress'].extend(service_address_records)

        # Extract labor data
        labor_records = extract_wolabor_data(normalized, wonum, workorderid)
        processed_data['wolabor'].extend(labor_records)

        # Extract material data
        material_records = extract_womaterial_data(normalized, wonum, workorderid)
        processed_data['womaterial'].extend(material_records)

        # Extract tool data
        tool_records = extract_wotool_data(normalized, wonum, workorderid)
        processed_data['wotool'].extend(tool_records)

    # Log processing stats
    logger.info(f"Work order processing stats:")
    logger.info(f"  Total records: {stats['total']}")
    logger.info(f"  Skipped due to status (CAN/CLOSE): {stats['skipped_status']}")
    logger.info(f"  Skipped due to historyflag=1: {stats['skipped_historyflag']}")
    logger.info(f"  Skipped due to missing required fields: {stats['skipped_missing_fields']}")
    logger.info(f"  Successfully processed: {stats['processed']}")

    return processed_data

def sync_to_database(processed_data, db_path):
    """
    Synchronize the processed data to the SQLite database.

    Args:
        processed_data (dict): Processed data with tables and records
        db_path (str): Path to the SQLite database file

    Returns:
        dict: Sync results with counts of inserted/updated records
    """
    if not processed_data:
        logger.error("No processed data to sync")
        return None

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Initialize sync results
    sync_results = {
        'inserted': defaultdict(int),
        'updated': defaultdict(int),
        'errors': defaultdict(int),
        'total': defaultdict(int)
    }

    try:
        # Sync each table
        sync_tables = [
            'workorder',
            'woserviceaddress',
            'wolabor',
            'womaterial',
            'wotool'
        ]

        # First sync the main workorder table to ensure parent records exist
        if 'workorder' in processed_data and processed_data['workorder']:
            logger.info(f"Syncing {len(processed_data['workorder'])} records to workorder table")

            for record in processed_data['workorder']:
                sync_results['total']['workorder'] += 1

                try:
                    # Check if record exists
                    cursor.execute(
                        "SELECT COUNT(*) FROM workorder WHERE wonum = ? AND workorderid = ?",
                        (record['wonum'], record['workorderid'])
                    )

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = "WHERE wonum = ? AND workorderid = ?"
                        params = list(record.values()) + [record['wonum'], record['workorderid']]

                        cursor.execute(f"UPDATE workorder SET {set_clause} {where_clause}", params)
                        sync_results['updated']['workorder'] += 1
                    else:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO workorder ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted']['workorder'] += 1

                except Exception as e:
                    logger.error(f"Error syncing record to workorder: {str(e)}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors']['workorder'] += 1

        # Now sync the related tables
        for table in sync_tables[1:]:  # Skip 'workorder' as we already processed it
            if table not in processed_data or not processed_data[table]:
                logger.info(f"No data to sync for {table} table")
                continue

            logger.info(f"Syncing {len(processed_data[table])} records to {table} table")

            for record in processed_data[table]:
                sync_results['total'][table] += 1

                try:
                    # Define primary key fields for each table
                    if table == 'woserviceaddress':
                        pk_field = 'woserviceaddressid'
                        pk_value = record[pk_field]
                    elif table == 'wolabor':
                        pk_field = 'wolaborid'
                        pk_value = record[pk_field]
                    elif table == 'womaterial':
                        pk_field = 'womaterialid'
                        pk_value = record[pk_field]
                    elif table == 'wotool':
                        pk_field = 'wotoolid'
                        pk_value = record[pk_field]
                    else:
                        logger.warning(f"Unknown table {table}, skipping")
                        continue

                    # Check if record exists
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {pk_field} = ?", (pk_value,))

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = f"WHERE {pk_field} = ?"
                        params = list(record.values()) + [pk_value]

                        cursor.execute(f"UPDATE {table} SET {set_clause} {where_clause}", params)
                        sync_results['updated'][table] += 1
                    else:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO {table} ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted'][table] += 1

                except Exception as e:
                    logger.error(f"Error syncing record to {table}: {str(e)}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors'][table] += 1

        # Update sync_status table
        now = datetime.datetime.now().isoformat()
        total_records = sum(sync_results['total'].values())
        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("MXAPIWODETAIL", now, total_records, "success", "Sync completed successfully")
        )

        # Commit the transaction
        conn.commit()
        logger.info("Database transaction committed")

    except Exception as e:
        logger.error(f"Error during database sync: {str(e)}")
        conn.rollback()
        logger.error("Database transaction rolled back")
        return None

    finally:
        conn.close()

    return sync_results

def main():
    """Main function to fetch and sync work order data."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sync work order data from Maximo to local database')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Path to SQLite database')
    parser.add_argument('--site', help='Site ID to filter by')
    parser.add_argument('--force-full', action='store_true', help='Force full sync (ignore last sync time)')
    parser.add_argument('--limit', type=int, default=100, help='Maximum number of records to fetch')
    parser.add_argument('--status', help='Work order status to filter by')
    args = parser.parse_args()

    # Ensure API key is available
    if not API_KEY:
        logger.error("MAXIMO_API_KEY not found in .env file")
        sys.exit(1)

    # Get last sync time (unless force full sync)
    last_sync = None
    if not args.force_full:
        last_sync = get_last_sync_time(args.db_path)
        if last_sync:
            logger.info(f"Last sync time: {last_sync}")
        else:
            logger.info("No previous sync found, performing full sync")
    else:
        logger.info("Forcing full sync (ignoring last sync time)")

    # Define the statuses to sync
    statuses = ['WAPPR', 'APPR', 'INPRG', 'ASSIGN', 'WMATL']

    # If a specific status is provided, only sync that one
    if args.status and args.status in statuses:
        statuses = [args.status]

    # Initialize combined processed data
    combined_processed_data = {
        'workorder': [],
        'woserviceaddress': [],
        'wolabor': [],
        'womaterial': [],
        'wotool': []
    }

    # Fetch and process data for each status
    for status in statuses:
        logger.info(f"Fetching work orders with status {status}")

        # Fetch work order data for this status
        wodetail_data = fetch_wodetail_data(args.site, last_sync, args.limit, status)

        if not wodetail_data:
            logger.warning(f"No data found for status {status}")
            continue

        # Process the data
        processed_data = process_data(wodetail_data)

        if not processed_data:
            logger.warning(f"Failed to process work order data for status {status}")
            continue

        # Combine the processed data
        for table, records in processed_data.items():
            combined_processed_data[table].extend(records)

    # Check if we have any data to sync
    if not any(combined_processed_data.values()):
        logger.error("No work order data to sync")
        return

    # Sync to database
    sync_results = sync_to_database(combined_processed_data, args.db_path)

    if not sync_results:
        logger.error("Failed to sync work order data to database")
        return

    # Print sync results
    logger.info("Sync completed successfully")
    logger.info(f"Work orders: {sync_results['inserted']['workorder']} inserted, {sync_results['updated']['workorder']} updated")
    logger.info(f"Service addresses: {sync_results['inserted']['woserviceaddress']} inserted, {sync_results['updated']['woserviceaddress']} updated")
    logger.info(f"Labor: {sync_results['inserted']['wolabor']} inserted, {sync_results['updated']['wolabor']} updated")
    logger.info(f"Materials: {sync_results['inserted']['womaterial']} inserted, {sync_results['updated']['womaterial']} updated")
    logger.info(f"Tools: {sync_results['inserted']['wotool']} inserted, {sync_results['updated']['wotool']} updated")
    logger.info(f"Total records processed: {sum(sync_results['total'].values())}")

if __name__ == "__main__":
    main()
