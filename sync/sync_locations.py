#!/usr/bin/env python3
"""
Script to synchronize data from the MXAPILOCATIONS endpoint to the local SQLite database.
This script will:
1. Fetch data from MXAPILOCATIONS endpoint with status="OPERATING"
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
logger = logging.getLogger('sync_locations')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_locations_data(site=None, last_sync=None, limit=500):
    """
    Fetch data from MXAPILOCATIONS endpoint with status="OPERATING".

    Args:
        site (str): Site ID to filter by
        last_sync (str): ISO format timestamp of last sync
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API with detailed locations data
    """
    # Prepare API endpoint
    endpoint = f"{BASE_URL}/api/os/mxapilocations"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*",  # Request all fields
        "oslc.where": "status=\"OPERATING\""  # Filter for operating locations
    }

    # Add site filter if provided
    if site:
        query_params["oslc.where"] += f" and siteid=\"{site}\""

    # If we have a last sync time, add it to the query to get only changes
    if last_sync:
        # Format: changedate>="2023-01-01T00:00:00-00:00"
        query_params["oslc.where"] += f" and changedate>=\"{last_sync}\""

    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY  # Using the API key from .env
    }

    logger.info(f"Fetching location data from {endpoint}")
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
            logger.info(f"Successfully fetched location data. Status code: {response.status_code}")

            # Save the raw response for debugging
            with open('locations_sync_response.json', 'w') as f:
                f.write(response.text)

            # Parse the JSON response
            try:
                data = response.json()

                # Check for member key
                if 'member' in data:
                    logger.info(f"Found {len(data['member'])} location records")
                    return data
                elif 'rdfs:member' in data:
                    logger.info(f"Found {len(data['rdfs:member'])} location records")
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
            logger.error(f"Error fetching location data. Status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        logger.error(f"Exception during location request: {str(e)}")
        return None

def process_location_data(data):
    """
    Process and transform the location data to match our database schema.

    Args:
        data (dict): JSON response from the API

    Returns:
        dict: Processed data with tables and records
    """
    if not data:
        logger.error("No data to process")
        return None

    # Check if there are no records but the response is valid
    if 'member' not in data or not data['member']:
        logger.info("No new location records to process")
        # Return empty but valid processed data structure
        return {
            'locations': []
        }

    # Initialize containers for each table
    processed_data = {
        'locations': []
    }

    # Track unique IDs to avoid duplicates
    seen_ids = {
        'locations': set()
    }

    # Process each location record
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

        # Extract location data
        location_record = extract_location_data(normalized_record)
        if location_record and location_record['location'] not in seen_ids['locations']:
            processed_data['locations'].append(location_record)
            seen_ids['locations'].add(location_record['location'])

    # Log summary of processed data
    for table, records in processed_data.items():
        logger.info(f"Processed {len(records)} records for {table} table")

    return processed_data

def extract_location_data(record):
    """Extract location data from a normalized record."""
    location_fields = [
        'location', 'description', 'status', 'siteid', 'orgid', 'type', 'type_description',
        'glaccount', 'changeby', 'changedate', 'disabled', 'failurecode', 'locationsid',
        'locationuid', 'pluscpmextdate', 'pluspcustomer', 'pluspcustomer_description',
        'serviceaddress', 'startasset', 'starttimermins', 'starttimermins_description',
        'systemid', 'useinpopr', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'location' not in record:
        logger.warning("Record missing location, skipping")
        return None

    # Create location record with available fields
    location_record = {field: record.get(field) for field in location_fields if field in record}

    # Add sync metadata
    location_record['_last_sync'] = datetime.datetime.now().isoformat()
    location_record['_sync_status'] = 'synced'

    return location_record

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

    # Initialize sync results
    sync_results = {
        'inserted': defaultdict(int),
        'updated': defaultdict(int),
        'errors': defaultdict(int),
        'total': defaultdict(int)
    }

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    try:
        # Sync each table
        sync_tables = [
            'locations'
        ]

        for table in sync_tables:
            if table not in processed_data or not processed_data[table]:
                logger.info(f"No data to sync for {table} table")
                continue

            logger.info(f"Syncing {len(processed_data[table])} records to {table} table")

            for record in processed_data[table]:
                sync_results['total'][table] += 1

                try:
                    # Check if record exists
                    if table == 'locations':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE location = ?", (record['location'],))

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = ""

                        if table == 'locations':
                            where_clause = "WHERE location = ?"
                            params = list(record.values()) + [record['location']]

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

        # Update sync_status table with the total count of records in the table
        now = datetime.datetime.now().isoformat()

        # Get the total count of records in the locations table
        cursor.execute("SELECT COUNT(*) FROM locations")
        total_count = cursor.fetchone()[0]
        logger.info(f"Total count of records in locations table: {total_count}")

        # Create a more informative message
        new_records = sync_results['inserted']['locations']
        updated_records = sync_results['updated']['locations']
        message = f"Existing records: {total_count - new_records}, Newly added: {new_records}, Updated: {updated_records}, Total: {total_count}"
        logger.info(message)

        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("MXAPILOCATIONS", now, total_count, "success", message)
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
    Get the timestamp of the last successful sync for MXAPILOCATIONS.

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
        cursor.execute("SELECT last_sync FROM sync_status WHERE endpoint = 'MXAPILOCATIONS' AND status = 'success'")
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
    """Main function to synchronize MXAPILOCATIONS data."""
    parser = argparse.ArgumentParser(description='Synchronize MXAPILOCATIONS data to local database')
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

    # Fetch location data
    locations_data = fetch_locations_data(site=site, last_sync=last_sync, limit=args.limit)

    if not locations_data:
        logger.error("Failed to fetch location data")
        return

    # Process the data
    processed_data = process_location_data(locations_data)

    if not processed_data:
        logger.error("Failed to process location data")
        return

    # Sync to database
    sync_results = sync_to_database(processed_data, db_path)

    if not sync_results:
        logger.error("Failed to sync location data to database")
        return

    # If we have no records but the sync was successful, it means there were no changes
    if sync_results['total']['locations'] == 0:
        logger.info("No new location records to sync")

        # Update sync_status table to record the sync attempt, but get the actual count of records in the table
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get the actual count of records in the locations table
            cursor.execute("SELECT COUNT(*) FROM locations")
            actual_count = cursor.fetchone()[0]
            logger.info(f"Actual count of records in locations table: {actual_count}")

            # Create a more informative message
            message = f"Existing records: {actual_count}, Newly added: 0, Updated: 0, Total: {actual_count}"
            logger.info(message)

            now = datetime.datetime.now().isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
                ("MXAPILOCATIONS", now, actual_count, "success", message)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating sync status: {e}")
            # Continue anyway

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
