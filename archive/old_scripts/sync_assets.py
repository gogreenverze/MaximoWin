#!/usr/bin/env python3
"""
Script to synchronize data from the MXAPIASSET endpoint to the local SQLite database.
This script will:
1. Fetch data from MXAPIASSET endpoint with status in ("OPERATING", "ACTIVE")
2. Process and transform the data to match our database schema
3. Insert/update the records in our local database
4. Update the sync_status table with the synchronization results
"""
import os
import sys
import json
import sqlite3
import requests
import time
import datetime
from collections import defaultdict
from dotenv import load_dotenv
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sync_assets')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_assets_data(site=None, last_sync=None, limit=500):
    """
    Fetch data from MXAPIASSET endpoint with status in ("OPERATING", "ACTIVE").

    Args:
        site (str): Site ID to filter by
        last_sync (str): ISO format timestamp of last sync
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API with detailed assets data
    """
    # Try both API endpoint formats
    endpoints = [
        f"{BASE_URL}/api/os/mxapiasset",  # Standard REST API format
        f"{BASE_URL}/oslc/os/mxapiasset"  # OSLC format
    ]

    # We'll try each endpoint until one works
    endpoint = endpoints[0]

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*",  # Request all fields
        "oslc.childrenExpand": "true",  # Include child objects
        "collectioncount": "1",  # Include count of child collections
        "ignorecollectionref": "0",  # Don't ignore collection references
        "relativeuri": "1"  # Use relative URIs for child objects
    }

    # Add specific child objects to include
    # These are the related tables we want to retrieve along with the asset
    child_objects = [
        "assetmeter",  # Asset meters
        "assetspec",   # Asset specifications
        "doclinks",    # Document attachments
        "failurereport" # Failure reports
    ]

    # Add the child objects to the query
    query_params["oslc.select"] = "*,assetmeter{*},assetspec{*},doclinks{*},failurereport{*}"

    # Use a simpler where clause approach
    # Just filter by status="OPERATING" and site if provided
    if site:
        query_params["oslc.where"] = f"status=\"OPERATING\" and siteid=\"{site}\""
    else:
        query_params["oslc.where"] = "status=\"OPERATING\""

    # If we have a last sync time, add it to the query to get only changes
    if last_sync:
        # Format: changedate>="2023-01-01T00:00:00-00:00"
        query_params["oslc.where"] += f" and changedate>=\"{last_sync}\""

    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY  # Using the API key from .env
    }

    # Try each endpoint until one works
    for endpoint in endpoints:
        logger.info(f"Fetching asset data from {endpoint}")
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
                logger.info(f"Successfully fetched asset data. Status code: {response.status_code}")

                # Save the raw response for debugging
                with open('assets_sync_response.json', 'w') as f:
                    f.write(response.text)

                # Parse the JSON response
                try:
                    data = response.json()

                    # Check for member key
                    if 'member' in data:
                        logger.info(f"Found {len(data['member'])} asset records")
                        return data
                    elif 'rdfs:member' in data:
                        logger.info(f"Found {len(data['rdfs:member'])} asset records")
                        # Standardize the data structure
                        data['member'] = data['rdfs:member']
                        return data
                    else:
                        logger.warning(f"No member data found in response. Keys: {list(data.keys())}")
                        # Continue to next endpoint
                        continue

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
                    logger.warning(f"Response text: {response.text[:500]}")
                    # Continue to next endpoint
                    continue
            else:
                logger.warning(f"Error fetching asset data from {endpoint}. Status code: {response.status_code}")
                logger.warning(f"Response: {response.text[:500]}")
                # Continue to next endpoint
                continue

        except Exception as e:
            logger.warning(f"Exception during asset request to {endpoint}: {str(e)}")
            # Continue to next endpoint
            continue

    # If we get here, all endpoints failed
    logger.error("All endpoints failed to fetch asset data")
    return None

def process_asset_data(data):
    """
    Process and transform the asset data to match our database schema.

    Args:
        data (dict): JSON response from the API

    Returns:
        dict: Processed data with tables and records
    """
    if not data or 'member' not in data or not data['member']:
        logger.error("No data to process")
        return None

    # Initialize containers for each table
    processed_data = {
        'assets': [],
        'assetmeter': [],
        'assetspec': [],
        'assetdoclinks': [],
        'assetfailure': []
    }

    # Track unique IDs to avoid duplicates
    seen_ids = {
        'assets': set(),
        'assetmeter': set(),
        'assetspec': set(),
        'assetdoclinks': set(),
        'assetfailure': set()
    }

    # Process each asset record
    for record in data['member']:
        # Normalize field names (remove prefixes)
        normalized_record = {}
        for field, value in record.items():
            # Remove common prefixes like 'spi:' or 'rdf:'
            normalized_field = field
            for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                if field.startswith(prefix):
                    normalized_field = field[len(prefix):]
                    break

            normalized_record[normalized_field] = value

        # Extract asset data
        asset_record = extract_asset_data(normalized_record)
        if asset_record and asset_record['assetnum'] not in seen_ids['assets']:
            processed_data['assets'].append(asset_record)
            seen_ids['assets'].add(asset_record['assetnum'])

            # Process child objects if they exist
            assetnum = asset_record['assetnum']
            siteid = asset_record['siteid']

            # Process asset meters
            if 'assetmeter' in normalized_record:
                meters = normalized_record['assetmeter']
                if isinstance(meters, list):
                    for meter in meters:
                        meter_record = extract_assetmeter_data(meter, assetnum, siteid)
                        if meter_record:
                            meter_key = f"{assetnum}_{siteid}_{meter_record['metername']}"
                            if meter_key not in seen_ids['assetmeter']:
                                processed_data['assetmeter'].append(meter_record)
                                seen_ids['assetmeter'].add(meter_key)

            # Process asset specifications
            if 'assetspec' in normalized_record:
                specs = normalized_record['assetspec']
                if isinstance(specs, list):
                    for spec in specs:
                        spec_record = extract_assetspec_data(spec, assetnum, siteid)
                        if spec_record:
                            spec_key = f"{assetnum}_{siteid}_{spec_record['assetattrid']}"
                            if spec_key not in seen_ids['assetspec']:
                                processed_data['assetspec'].append(spec_record)
                                seen_ids['assetspec'].add(spec_key)

            # Process document links
            if 'doclinks' in normalized_record:
                docs = normalized_record['doclinks']
                if isinstance(docs, list):
                    for doc in docs:
                        doc_record = extract_doclinks_data(doc, assetnum, siteid)
                        if doc_record and doc_record['docinfoid'] not in seen_ids['assetdoclinks']:
                            processed_data['assetdoclinks'].append(doc_record)
                            seen_ids['assetdoclinks'].add(doc_record['docinfoid'])

            # Process failure reports
            if 'failurereport' in normalized_record:
                failures = normalized_record['failurereport']
                if isinstance(failures, list):
                    for failure in failures:
                        failure_record = extract_failure_data(failure, assetnum, siteid)
                        if failure_record and failure_record['failurereportid'] not in seen_ids['assetfailure']:
                            processed_data['assetfailure'].append(failure_record)
                            seen_ids['assetfailure'].add(failure_record['failurereportid'])

    # Log summary of processed data
    for table, records in processed_data.items():
        logger.info(f"Processed {len(records)} records for {table} table")

    return processed_data

def extract_asset_data(record):
    """Extract asset data from a normalized record."""
    asset_fields = [
        'assetnum', 'description', 'status', 'siteid', 'orgid', 'location', 'parent',
        'serialnum', 'changeby', 'changedate', 'disabled', 'assetid', 'assettag',
        'isrunning', 'moved', 'priority', 'purchaseprice', 'replacecost', 'totalcost',
        'vendor', 'manufacturer', 'installdate', 'status_description', 'type_description',
        'type', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'assetnum' not in record or 'siteid' not in record:
        logger.warning("Record missing assetnum or siteid, skipping")
        return None

    # Create asset record with available fields
    asset_record = {field: record.get(field) for field in asset_fields if field in record}

    # Add sync metadata
    asset_record['_last_sync'] = datetime.datetime.now().isoformat()
    asset_record['_sync_status'] = 'synced'

    return asset_record

def extract_assetmeter_data(record, assetnum, siteid):
    """
    Extract asset meter data from a normalized record.

    Args:
        record (dict): The asset meter record
        assetnum (str): The asset number
        siteid (str): The site ID

    Returns:
        dict: Processed asset meter record
    """
    meter_fields = [
        'metername', 'active', 'lastreading', 'lastreadingdate', 'lastreadinginspctr',
        'remarks', 'meter_description', 'meter_measureunitid', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'metername' not in record:
        logger.warning("Asset meter record missing metername, skipping")
        return None

    # Create meter record with available fields
    meter_record = {field: record.get(field) for field in meter_fields if field in record}

    # Add asset reference
    meter_record['assetnum'] = assetnum
    meter_record['siteid'] = siteid

    # Add sync metadata
    meter_record['_last_sync'] = datetime.datetime.now().isoformat()
    meter_record['_sync_status'] = 'synced'

    return meter_record

def extract_assetspec_data(record, assetnum, siteid):
    """
    Extract asset specification data from a normalized record.

    Args:
        record (dict): The asset specification record
        assetnum (str): The asset number
        siteid (str): The site ID

    Returns:
        dict: Processed asset specification record
    """
    spec_fields = [
        'assetattrid', 'alnvalue', 'numvalue', 'datevalue', 'changeby', 'changedate',
        'assetattribute_description', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'assetattrid' not in record:
        logger.warning("Asset spec record missing assetattrid, skipping")
        return None

    # Create spec record with available fields
    spec_record = {field: record.get(field) for field in spec_fields if field in record}

    # Add asset reference
    spec_record['assetnum'] = assetnum
    spec_record['siteid'] = siteid

    # Add sync metadata
    spec_record['_last_sync'] = datetime.datetime.now().isoformat()
    spec_record['_sync_status'] = 'synced'

    return spec_record

def extract_doclinks_data(record, assetnum, siteid):
    """
    Extract document links data from a normalized record.

    Args:
        record (dict): The document links record
        assetnum (str): The asset number
        siteid (str): The site ID

    Returns:
        dict: Processed document links record
    """
    doclinks_fields = [
        'docinfoid', 'document', 'description', 'createdate', 'changeby',
        'ownertable', 'ownerid', 'urltype', 'urlname', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'docinfoid' not in record:
        logger.warning("Document links record missing docinfoid, skipping")
        return None

    # Create doclinks record with available fields
    doclinks_record = {field: record.get(field) for field in doclinks_fields if field in record}

    # Add asset reference
    doclinks_record['assetnum'] = assetnum
    doclinks_record['siteid'] = siteid

    # Add sync metadata
    doclinks_record['_last_sync'] = datetime.datetime.now().isoformat()
    doclinks_record['_sync_status'] = 'synced'

    return doclinks_record

def extract_failure_data(record, assetnum, siteid):
    """
    Extract failure report data from a normalized record.

    Args:
        record (dict): The failure report record
        assetnum (str): The asset number
        siteid (str): The site ID

    Returns:
        dict: Processed failure report record
    """
    failure_fields = [
        'failurereportid', 'failurecode', 'failuredate', 'problemcode', 'causecode',
        'remedycode', 'remarks', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'failurereportid' not in record:
        logger.warning("Failure report record missing failurereportid, skipping")
        return None

    # Create failure record with available fields
    failure_record = {field: record.get(field) for field in failure_fields if field in record}

    # Add asset reference
    failure_record['assetnum'] = assetnum
    failure_record['siteid'] = siteid

    # Add sync metadata
    failure_record['_last_sync'] = datetime.datetime.now().isoformat()
    failure_record['_sync_status'] = 'synced'

    return failure_record

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
            'assets',
            'assetmeter',
            'assetspec',
            'assetdoclinks',
            'assetfailure'
        ]

        # First sync the main assets table to ensure parent records exist
        if 'assets' in processed_data and processed_data['assets']:
            logger.info(f"Syncing {len(processed_data['assets'])} records to assets table")

            for record in processed_data['assets']:
                sync_results['total']['assets'] += 1

                try:
                    # Check if record exists
                    cursor.execute("SELECT COUNT(*) FROM assets WHERE assetnum = ? AND siteid = ?",
                                  (record['assetnum'], record['siteid']))

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = "WHERE assetnum = ? AND siteid = ?"
                        params = list(record.values()) + [record['assetnum'], record['siteid']]

                        cursor.execute(f"UPDATE assets SET {set_clause} {where_clause}", params)
                        sync_results['updated']['assets'] += 1
                    else:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO assets ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted']['assets'] += 1

                except Exception as e:
                    logger.error(f"Error syncing record to assets: {str(e)}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors']['assets'] += 1

        # Now sync the related tables
        for table in sync_tables[1:]:  # Skip 'assets' as we already processed it
            if table not in processed_data or not processed_data[table]:
                logger.info(f"No data to sync for {table} table")
                continue

            logger.info(f"Syncing {len(processed_data[table])} records to {table} table")

            for record in processed_data[table]:
                sync_results['total'][table] += 1

                try:
                    # Define primary key fields for each table
                    if table == 'assetmeter':
                        pk_fields = ['assetnum', 'siteid', 'metername']
                        pk_values = [record['assetnum'], record['siteid'], record['metername']]
                    elif table == 'assetspec':
                        pk_fields = ['assetnum', 'siteid', 'assetattrid']
                        pk_values = [record['assetnum'], record['siteid'], record['assetattrid']]
                    elif table == 'assetdoclinks':
                        pk_fields = ['docinfoid']
                        pk_values = [record['docinfoid']]
                    elif table == 'assetfailure':
                        pk_fields = ['failurereportid']
                        pk_values = [record['failurereportid']]
                    else:
                        logger.warning(f"Unknown table {table}, skipping")
                        continue

                    # Check if record exists
                    where_clause = " AND ".join([f"{field} = ?" for field in pk_fields])
                    cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_clause}", pk_values)

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = " AND ".join([f"{field} = ?" for field in pk_fields])
                        params = list(record.values()) + pk_values

                        cursor.execute(f"UPDATE {table} SET {set_clause} WHERE {where_clause}", params)
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
            ("MXAPIASSET", now, total_records, "success", "Sync completed successfully")
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

def get_last_sync(db_path):
    """
    Get the timestamp of the last successful sync for MXAPIASSET.

    Args:
        db_path (str): Path to the SQLite database file

    Returns:
        str: ISO format timestamp of last sync or None if no previous sync
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query the sync_status table
        cursor.execute("SELECT last_sync FROM sync_status WHERE endpoint = 'MXAPIASSET' AND status = 'success'")
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]
        else:
            return None

    except Exception as e:
        logger.error(f"Error getting last sync timestamp: {str(e)}")
        return None

def get_default_site(db_path):
    """
    Get the default site for the current user from the database.

    Args:
        db_path (str): Path to the SQLite database file

    Returns:
        str: Default site ID or None if not found
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query for a default site
        # This assumes we have at least one user with a default site
        cursor.execute("""
            SELECT ps.siteid
            FROM person_site ps
            WHERE ps.isdefault = 1
            LIMIT 1
        """)
        result = cursor.fetchone()

        conn.close()

        if result:
            return result[0]
        else:
            logger.warning("No default site found in database")
            return None

    except Exception as e:
        logger.error(f"Error getting default site: {str(e)}")
        return None

def main():
    """Main function to synchronize MXAPIASSET data."""
    parser = argparse.ArgumentParser(description='Synchronize MXAPIASSET data to local database')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
    parser.add_argument('--site', type=str, default=None,
                        help='Site ID to filter by (defaults to user\'s default site)')
    parser.add_argument('--limit', type=int, default=500,
                        help='Maximum number of records to fetch')
    parser.add_argument('--force-full', action='store_true',
                        help='Force a full sync instead of incremental')

    args = parser.parse_args()

    # Expand the path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        logger.error("Please run create_maximo_db.py first")
        return

    # Get site to filter by
    site = args.site
    if not site:
        site = get_default_site(db_path)
        if not site:
            logger.error("No site specified and no default site found in database")
            return

    logger.info(f"Using site filter: {site}")

    # Get last sync timestamp if not doing a full sync
    last_sync = None
    if not args.force_full:
        last_sync = get_last_sync(db_path)
        if last_sync:
            logger.info(f"Performing incremental sync since {last_sync}")
        else:
            logger.info("No previous sync found, performing full sync")
    else:
        logger.info("Forced full sync requested")

    # Fetch asset data
    assets_data = fetch_assets_data(site=site, last_sync=last_sync, limit=args.limit)

    if not assets_data:
        logger.error("Failed to fetch asset data")
        return

    # Process the data
    processed_data = process_asset_data(assets_data)

    if not processed_data:
        logger.error("Failed to process asset data")
        return

    # Sync to database
    sync_results = sync_to_database(processed_data, db_path)

    if not sync_results:
        logger.error("Failed to sync asset data to database")
        return

    # Print summary
    print("\n=== SYNC SUMMARY ===\n")
    for table in sync_results['total']:
        print(f"{table}:")
        print(f"  Total: {sync_results['total'][table]}")
        print(f"  Inserted: {sync_results['inserted'][table]}")
        print(f"  Updated: {sync_results['updated'][table]}")
        print(f"  Errors: {sync_results['errors'][table]}")
        print()

    logger.info("Synchronization complete")

if __name__ == "__main__":
    main()
