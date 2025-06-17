#!/usr/bin/env python3
"""
Script to synchronize inventory data from MXAPIINVENTORY endpoint to local SQLite database.
This script will:
1. Load API key from .env file
2. Fetch data from MXAPIINVENTORY endpoint with status="ACTIVE"
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
logger = logging.getLogger('sync_inventory')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_inventory_data(site=None, last_sync=None, limit=100):
    """
    Fetch inventory data from MXAPIINVENTORY endpoint with status="ACTIVE".

    Args:
        site (str): Site ID to filter by
        last_sync (str): Last sync time in ISO format
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API
    """
    endpoint = f"{BASE_URL}/api/os/mxapiinventory"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*"  # Request all fields
    }

    # Build the filter
    # Start with the status filter
    base_filter = "status=\"ACTIVE\""

    # Add site filter if provided
    if site:
        base_filter += f" and siteid=\"{site}\""

    query_params["oslc.where"] = base_filter

    # If we have a last sync time, log it but don't use it in the query
    # The MXAPIINVENTORY endpoint might not support filtering by changedate
    if last_sync:
        logger.info(f"Last sync time: {last_sync} (not used in query - full sync will be performed)")

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
        logger.info(f"Fetching inventory data from {endpoint}")
        logger.info(f"Query parameters: {json.dumps(query_params, indent=2)}")

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
                        return None
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response")
                return None
        else:
            logger.warning(f"Request failed with status code: {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        logger.warning(f"Request exception: {str(e)}")
        return None

def normalize_record(record):
    """
    Normalize a record by removing prefixes from field names.

    Args:
        record (dict): Raw record from API

    Returns:
        dict: Normalized record
    """
    normalized = {}

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

def extract_inventory_data(record):
    """
    Extract inventory data from a normalized record.

    Args:
        record (dict): Normalized record

    Returns:
        dict: Extracted inventory data
    """
    # Required fields for inventory
    required_fields = ['itemnum', 'siteid', 'location']

    # Check if all required fields are present
    for field in required_fields:
        if field not in record:
            logger.warning(f"Required field '{field}' missing from record")
            return None

    # Fields to extract for inventory table
    inventory_fields = [
        'itemnum', 'siteid', 'location', 'description', 'status',
        'curbal', 'binnum', 'lotnum', 'orgid', 'itemsetid',
        'issueunit', 'storeloc', 'itemtype', 'itemtype_description',
        'rotating', 'conditioncode', 'conditioncode_description',
        'changeby', 'changedate', '_rowstamp', 'inventoryid', 'about',
        'asl', 'autocalcrop', 'avblbalance', 'benchstock', 'bincnt',
        'ccf', 'consignment', 'costtype', 'costtype_description',
        'curbaltotal', 'deliverytime', 'expiredqty', 'hardresissue',
        'haschildinvbalance', 'internal', 'invreserveqty', 'issue1yrago',
        'issue2yrago', 'issue3yrago', 'issueytd', 'lastissuedate',
        'maxlevel', 'minlevel', 'orderqty', 'orderunit', 'reorder',
        'reservedqty', 'shippedqty', 'stagedqty', 'status_description',
        'statusdate', 'statusiface', 'vecatc', 'veccritical', 'vendor'
    ]

    # Create inventory record with available fields
    inventory_record = {field: record.get(field) for field in inventory_fields if field in record}

    # Add sync metadata
    inventory_record['_last_sync'] = datetime.datetime.now().isoformat()
    inventory_record['_sync_status'] = 'synced'

    return inventory_record

def extract_invbalances_data(record, inventoryid):
    """
    Extract invbalances data from a normalized record.

    Args:
        record (dict): Normalized record
        inventoryid (int): Parent inventory ID

    Returns:
        list: Extracted invbalances data
    """
    if 'invbalances' not in record or not record['invbalances']:
        return []

    invbalances_records = []

    for invbalance in record['invbalances']:
        # Normalize the invbalance record
        normalized_invbalance = normalize_record(invbalance)

        # Create invbalances record
        invbalances_record = {
            'inventoryid': inventoryid,
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add all fields from the normalized record
        for field, value in normalized_invbalance.items():
            if field not in ['_rowstamp', '_last_sync', '_sync_status']:
                invbalances_record[field] = value

        invbalances_records.append(invbalances_record)

    return invbalances_records

def extract_invcost_data(record, inventoryid):
    """
    Extract invcost data from a normalized record.

    Args:
        record (dict): Normalized record
        inventoryid (int): Parent inventory ID

    Returns:
        list: Extracted invcost data
    """
    if 'invcost' not in record or not record['invcost']:
        return []

    invcost_records = []

    for invcost in record['invcost']:
        # Normalize the invcost record
        normalized_invcost = normalize_record(invcost)

        # Create invcost record
        invcost_record = {
            'inventoryid': inventoryid,
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add all fields from the normalized record
        for field, value in normalized_invcost.items():
            if field not in ['_rowstamp', '_last_sync', '_sync_status']:
                invcost_record[field] = value

        invcost_records.append(invcost_record)

    return invcost_records

def extract_itemcondition_data(record, inventoryid):
    """
    Extract itemcondition data from a normalized record.

    Args:
        record (dict): Normalized record
        inventoryid (int): Parent inventory ID

    Returns:
        list: Extracted itemcondition data
    """
    if 'itemcondition' not in record or not record['itemcondition']:
        return []

    itemcondition_records = []

    for itemcondition in record['itemcondition']:
        # Normalize the itemcondition record
        normalized_itemcondition = normalize_record(itemcondition)

        # Create itemcondition record
        itemcondition_record = {
            'inventoryid': inventoryid,
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add all fields from the normalized record
        for field, value in normalized_itemcondition.items():
            if field not in ['_rowstamp', '_last_sync', '_sync_status']:
                itemcondition_record[field] = value

        itemcondition_records.append(itemcondition_record)

    return itemcondition_records

def extract_matrectrans_data(record, inventoryid):
    """
    Extract matrectrans data from a normalized record.

    Args:
        record (dict): Normalized record
        inventoryid (int): Parent inventory ID

    Returns:
        list: Extracted matrectrans data
    """
    if 'matrectrans' not in record or not record['matrectrans']:
        return []

    matrectrans_records = []

    for matrectrans in record['matrectrans']:
        # Normalize the matrectrans record
        normalized_matrectrans = normalize_record(matrectrans)

        # Create matrectrans record
        matrectrans_record = {
            'inventoryid': inventoryid,
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add all fields from the normalized record
        for field, value in normalized_matrectrans.items():
            if field not in ['_rowstamp', '_last_sync', '_sync_status']:
                matrectrans_record[field] = value

        matrectrans_records.append(matrectrans_record)

    return matrectrans_records

def extract_transfercuritem_data(record, inventoryid):
    """
    Extract transfercuritem data from a normalized record.

    Args:
        record (dict): Normalized record
        inventoryid (int): Parent inventory ID

    Returns:
        list: Extracted transfercuritem data
    """
    if 'transfercuritem' not in record or not record['transfercuritem']:
        return []

    transfercuritem_records = []

    for transfercuritem in record['transfercuritem']:
        # Normalize the transfercuritem record
        normalized_transfercuritem = normalize_record(transfercuritem)

        # Create transfercuritem record
        transfercuritem_record = {
            'inventoryid': inventoryid,
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add all fields from the normalized record
        for field, value in normalized_transfercuritem.items():
            if field not in ['_rowstamp', '_last_sync', '_sync_status']:
                transfercuritem_record[field] = value

        transfercuritem_records.append(transfercuritem_record)

    return transfercuritem_records

def process_data(data):
    """
    Process and normalize the inventory data.

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
        'inventory': [],
        'inventory_invbalances': [],
        'inventory_invcost': [],
        'inventory_itemcondition': [],
        'inventory_matrectrans': [],
        'inventory_transfercuritem': []
    }

    # Track record processing stats
    stats = {
        'total': len(data['member']),
        'skipped_status': 0,
        'skipped_missing_fields': 0,
        'processed': 0
    }

    # Process each inventory record
    for record in data['member']:
        # Skip records with status other than ACTIVE
        if record.get('spi:status', record.get('status')) != 'ACTIVE':
            stats['skipped_status'] += 1
            continue

        # Normalize the record
        normalized = normalize_record(record)

        # Extract inventory record
        inventory_record = extract_inventory_data(normalized)

        if not inventory_record:
            stats['skipped_missing_fields'] += 1
            continue

        # Add to processed data
        processed_data['inventory'].append(inventory_record)

        # Get the inventory ID for related records
        inventoryid = inventory_record.get('inventoryid')

        if inventoryid:
            # Extract and add related records
            processed_data['inventory_invbalances'].extend(extract_invbalances_data(normalized, inventoryid))
            processed_data['inventory_invcost'].extend(extract_invcost_data(normalized, inventoryid))
            processed_data['inventory_itemcondition'].extend(extract_itemcondition_data(normalized, inventoryid))
            processed_data['inventory_matrectrans'].extend(extract_matrectrans_data(normalized, inventoryid))
            processed_data['inventory_transfercuritem'].extend(extract_transfercuritem_data(normalized, inventoryid))

        stats['processed'] += 1

    logger.info(f"Processed {stats['processed']} of {stats['total']} inventory records")
    logger.info(f"Skipped {stats['skipped_status']} records with non-ACTIVE status")
    logger.info(f"Skipped {stats['skipped_missing_fields']} records with missing required fields")

    # Log related records
    logger.info(f"Extracted {len(processed_data['inventory_invbalances'])} invbalances records")
    logger.info(f"Extracted {len(processed_data['inventory_invcost'])} invcost records")
    logger.info(f"Extracted {len(processed_data['inventory_itemcondition'])} itemcondition records")
    logger.info(f"Extracted {len(processed_data['inventory_matrectrans'])} matrectrans records")
    logger.info(f"Extracted {len(processed_data['inventory_transfercuritem'])} transfercuritem records")

    return processed_data

def get_last_sync_time(db_path):
    """
    Get the last sync time for the MXAPIINVENTORY endpoint.

    Args:
        db_path (str): Path to the SQLite database

    Returns:
        str: Last sync time in ISO format, or None if not found
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT last_sync FROM sync_status WHERE endpoint = 'MXAPIINVENTORY'")
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]
        else:
            return None
    except Exception as e:
        logger.error(f"Error getting last sync time: {e}")
        return None

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
        # First sync the main inventory table to ensure parent records exist
        if 'inventory' in processed_data and processed_data['inventory']:
            logger.info(f"Syncing {len(processed_data['inventory'])} records to inventory table")

            for record in processed_data['inventory']:
                sync_results['total']['inventory'] += 1

                try:
                    # Check if record exists
                    cursor.execute(
                        "SELECT COUNT(*) FROM inventory WHERE itemnum = ? AND siteid = ? AND location = ?",
                        (record['itemnum'], record['siteid'], record['location'])
                    )

                    count = cursor.fetchone()[0]

                    if count > 0:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys() if field not in ['itemnum', 'siteid', 'location']])
                        where_clause = "WHERE itemnum = ? AND siteid = ? AND location = ?"

                        # Build the parameter list (values for SET clause + values for WHERE clause)
                        params = [record[field] for field in record.keys() if field not in ['itemnum', 'siteid', 'location']]
                        params.extend([record['itemnum'], record['siteid'], record['location']])

                        cursor.execute(f"UPDATE inventory SET {set_clause} {where_clause}", params)
                        sync_results['updated']['inventory'] += 1
                    else:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO inventory ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted']['inventory'] += 1

                except Exception as e:
                    logger.error(f"Error syncing record to inventory table: {e}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors']['inventory'] += 1

        # Now sync the related tables
        related_tables = [
            'inventory_invbalances',
            'inventory_invcost',
            'inventory_itemcondition',
            'inventory_matrectrans',
            'inventory_transfercuritem'
        ]

        for table in related_tables:
            if table in processed_data and processed_data[table]:
                logger.info(f"Syncing {len(processed_data[table])} records to {table} table")

                # First delete existing records for these inventory IDs to avoid duplicates
                inventory_ids = list(set([record['inventoryid'] for record in processed_data[table]]))
                if inventory_ids:
                    placeholders = ", ".join(["?" for _ in inventory_ids])
                    cursor.execute(f"DELETE FROM {table} WHERE inventoryid IN ({placeholders})", inventory_ids)

                # Now insert all records
                for record in processed_data[table]:
                    sync_results['total'][table] += 1

                    try:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO {table} ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted'][table] += 1

                    except Exception as e:
                        logger.error(f"Error syncing record to {table} table: {e}")
                        logger.error(f"Record: {json.dumps(record)}")
                        sync_results['errors'][table] += 1

        # Update sync_status table
        now = datetime.datetime.now().isoformat()
        total_records = sum(sync_results['total'].values())

        # Get counts for each table
        new_records = sum(sync_results['inserted'].values())
        updated_records = sum(sync_results['updated'].values())

        # Create a more informative message
        message = f"Existing records: {total_records - new_records}, Newly added: {new_records}, Updated: {updated_records}, Total: {total_records}"
        logger.info(message)

        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("MXAPIINVENTORY", now, total_records, "success", message)
        )

        # Commit the transaction
        conn.commit()
        logger.info("Database transaction committed")

    except Exception as e:
        logger.error(f"Error during database sync: {e}")
        conn.rollback()
        logger.error("Database transaction rolled back")
        return None

    finally:
        conn.close()

    return sync_results

def main(args=None):
    """Main function to fetch and sync inventory data."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sync inventory data from Maximo to local database')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Path to SQLite database')
    parser.add_argument('--site', help='Site ID to filter by')
    parser.add_argument('--force-full', action='store_true', help='Force full sync (ignore last sync time)')
    parser.add_argument('--limit', type=int, default=100, help='Maximum number of records to fetch')

    if args:
        args = parser.parse_args(args)
    else:
        args = parser.parse_args()

    # Expand the database path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        logger.error("Please run create_maximo_db.py first")
        return

    # Get last sync time (unless force full sync)
    last_sync = None
    if not args.force_full:
        last_sync = get_last_sync_time(db_path)
        if last_sync:
            logger.info(f"Last sync time: {last_sync}")
        else:
            logger.info("No previous sync found, performing full sync")
    else:
        logger.info("Forcing full sync (ignoring last sync time)")

    # Fetch inventory data
    inventory_data = fetch_inventory_data(site=args.site, last_sync=last_sync, limit=args.limit)

    if not inventory_data:
        logger.error("Failed to fetch inventory data")
        return

    # Process the data
    processed_data = process_data(inventory_data)

    if not processed_data:
        logger.error("Failed to process inventory data")
        return

    # Sync to database
    sync_results = sync_to_database(processed_data, db_path)

    if not sync_results:
        logger.error("Failed to sync data to database")
        return

    # Print sync results
    print("\n=== SYNC RESULTS ===\n")
    print(f"Total records processed: {sum(sync_results['total'].values())}")
    print("\nInserted records:")
    for table, count in sync_results['inserted'].items():
        print(f"  {table}: {count}")

    print("\nUpdated records:")
    for table, count in sync_results['updated'].items():
        print(f"  {table}: {count}")

    print("\nErrors:")
    for table, count in sync_results['errors'].items():
        print(f"  {table}: {count}")

    logger.info("Inventory sync completed successfully")

if __name__ == "__main__":
    main()
