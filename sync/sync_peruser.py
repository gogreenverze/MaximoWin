#!/usr/bin/env python3
"""
Script to synchronize data from the MXAPIPERUSER endpoint to the local SQLite database.
This script will:
1. Fetch data from MXAPIPERUSER endpoint with status="ACTIVE"
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
logger = logging.getLogger('sync_peruser')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Ensure API key is available
if not API_KEY:
    logger.error("MAXIMO_API_KEY not found in .env file")
    sys.exit(1)

def fetch_peruser_data(last_sync=None, limit=500):
    """
    Fetch data from MXAPIPERUSER endpoint with status="ACTIVE".

    Args:
        last_sync (str): ISO format timestamp of last sync
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API with detailed peruser data
    """
    # Prepare API endpoint
    endpoint = f"{BASE_URL}/api/os/mxapiperuser"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*",  # Request all fields
        "oslc.where": "status=\"ACTIVE\""  # Filter for active users
    }

    # If we have a last sync time, log it but don't use it in the query
    # The changedate property is not available in the API
    if last_sync:
        logger.info(f"Last sync time: {last_sync} (not used in query - full sync will be performed)")
        # We'll just do a full sync of active users

    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY  # Using the API key from .env
    }

    logger.info(f"Fetching person data from {endpoint}")
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
            logger.info(f"Successfully fetched person data. Status code: {response.status_code}")

            # Save the raw response for debugging
            with open('peruser_sync_response.json', 'w') as f:
                f.write(response.text)

            # Parse the JSON response
            try:
                data = response.json()

                # Check for member key
                if 'member' in data:
                    logger.info(f"Found {len(data['member'])} person records")
                    return data
                elif 'rdfs:member' in data:
                    logger.info(f"Found {len(data['rdfs:member'])} person records")
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
            logger.error(f"Error fetching person data. Status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        logger.error(f"Exception during person request: {str(e)}")
        return None

def process_person_data(data):
    """
    Process and transform the person data to match our database schema.

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
        'person': [],
        'maxuser': [],
        'groupuser': [],
        'maxgroup': [],
        'groupuser_maxgroup': [],
        'person_site': []
    }

    # Track unique IDs to avoid duplicates
    seen_ids = {
        'person': set(),
        'maxuser': set(),
        'groupuser': set(),
        'maxgroup': set()
    }

    # Process each person record
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

        # Extract person data
        person_record = extract_person_data(normalized_record)
        if person_record and person_record['personid'] not in seen_ids['person']:
            processed_data['person'].append(person_record)
            seen_ids['person'].add(person_record['personid'])

            # Extract maxuser data if available
            if 'maxuser' in normalized_record:
                maxuser_data = normalized_record['maxuser']
                # Handle both object and array formats
                if isinstance(maxuser_data, dict):
                    maxuser_records = [maxuser_data]
                else:
                    maxuser_records = maxuser_data

                for maxuser_record in maxuser_records:
                    # Normalize maxuser field names
                    normalized_maxuser = {}
                    for field, value in maxuser_record.items():
                        normalized_field = field
                        for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                            if field.startswith(prefix):
                                normalized_field = field[len(prefix):]
                                break
                        normalized_maxuser[normalized_field] = value

                    # Extract and add maxuser record
                    mu_record = extract_maxuser_data(normalized_maxuser, person_record['personid'])
                    if mu_record and mu_record['maxuserid'] not in seen_ids['maxuser']:
                        processed_data['maxuser'].append(mu_record)
                        seen_ids['maxuser'].add(mu_record['maxuserid'])

                        # Extract groupuser data if available
                        if 'groupuser' in normalized_maxuser:
                            groupuser_data = normalized_maxuser['groupuser']
                            # Handle both object and array formats
                            if isinstance(groupuser_data, dict):
                                groupuser_records = [groupuser_data]
                            else:
                                groupuser_records = groupuser_data

                            for groupuser_record in groupuser_records:
                                # Normalize groupuser field names
                                normalized_groupuser = {}
                                for field, value in groupuser_record.items():
                                    normalized_field = field
                                    for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                                        if field.startswith(prefix):
                                            normalized_field = field[len(prefix):]
                                            break
                                    normalized_groupuser[normalized_field] = value

                                # Extract and add groupuser record
                                gu_record = extract_groupuser_data(normalized_groupuser, mu_record['maxuserid'])
                                if gu_record and gu_record['groupuserid'] not in seen_ids['groupuser']:
                                    processed_data['groupuser'].append(gu_record)
                                    seen_ids['groupuser'].add(gu_record['groupuserid'])

                                    # Extract maxgroup data if available
                                    if 'maxgroup' in normalized_groupuser:
                                        maxgroup_data = normalized_groupuser['maxgroup']

                                        # Handle both object and array formats
                                        if isinstance(maxgroup_data, dict):
                                            maxgroup_records = [maxgroup_data]
                                        else:
                                            maxgroup_records = maxgroup_data

                                        for maxgroup_record in maxgroup_records:
                                            # Normalize maxgroup field names
                                            normalized_maxgroup = {}
                                            for field, value in maxgroup_record.items():
                                                normalized_field = field
                                                for prefix in ['spi:', 'rdf:', 'oslc:', 'rdfs:']:
                                                    if field.startswith(prefix):
                                                        normalized_field = field[len(prefix):]
                                                        break
                                                normalized_maxgroup[normalized_field] = value

                                            # Extract and add maxgroup record
                                            mg_record = extract_maxgroup_data(normalized_maxgroup)
                                            if mg_record and mg_record['maxgroupid'] not in seen_ids['maxgroup']:
                                                processed_data['maxgroup'].append(mg_record)
                                                seen_ids['maxgroup'].add(mg_record['maxgroupid'])

                                            # Create groupuser_maxgroup relationship
                                            if mg_record:
                                                gm_record = {
                                                    'groupuserid': gu_record['groupuserid'],
                                                    'maxgroupid': mg_record['maxgroupid'],
                                                    '_last_sync': datetime.datetime.now().isoformat(),
                                                    '_sync_status': 'synced'
                                                }
                                                processed_data['groupuser_maxgroup'].append(gm_record)

                        # Extract person_site data
                        if 'defsite' in mu_record and mu_record['defsite']:
                            ps_record = {
                                'personid': person_record['personid'],
                                'siteid': mu_record['defsite'],
                                'isdefault': 1,
                                'isinsert': 0,
                                '_last_sync': datetime.datetime.now().isoformat(),
                                '_sync_status': 'synced'
                            }
                            processed_data['person_site'].append(ps_record)

                        if 'insertsite' in mu_record and mu_record['insertsite']:
                            # Check if we already added this site as default
                            if mu_record['insertsite'] != mu_record.get('defsite'):
                                ps_record = {
                                    'personid': person_record['personid'],
                                    'siteid': mu_record['insertsite'],
                                    'isdefault': 0,
                                    'isinsert': 1,
                                    '_last_sync': datetime.datetime.now().isoformat(),
                                    '_sync_status': 'synced'
                                }
                                processed_data['person_site'].append(ps_record)
                            else:
                                # Update the existing record to mark as both default and insert
                                for ps in processed_data['person_site']:
                                    if ps['personid'] == person_record['personid'] and ps['siteid'] == mu_record['insertsite']:
                                        ps['isinsert'] = 1
                                        break

    # Log summary of processed data
    for table, records in processed_data.items():
        logger.info(f"Processed {len(records)} records for {table} table")

    return processed_data

def extract_person_data(record):
    """Extract person data from a normalized record."""
    person_fields = [
        'personid', 'personuid', 'displayname', 'firstname', 'lastname',
        'title', 'status', 'status_description', 'statusdate', 'primaryemail',
        'primaryphone', 'locationorg', 'locationsite', 'location', 'country',
        'city', 'stateprovince', 'addressline1', 'postalcode', 'department',
        'supervisor', 'employeetype', 'employeetype_description', 'language',
        'timezone', 'timezone_description', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'personid' not in record:
        logger.warning("Record missing personid, skipping")
        return None

    # Create person record with available fields
    person_record = {field: record.get(field) for field in person_fields if field in record}

    # Add sync metadata
    person_record['_last_sync'] = datetime.datetime.now().isoformat()
    person_record['_sync_status'] = 'synced'

    return person_record

def extract_maxuser_data(record, personid):
    """Extract maxuser data from a normalized record."""
    maxuser_fields = [
        'maxuserid', 'userid', 'status', 'defsite', 'insertsite',
        'querywithsite', 'screenreader', 'failedlogins', 'sysuser',
        'type', 'type_description', 'loginid', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'maxuserid' not in record:
        logger.warning("Maxuser record missing maxuserid, skipping")
        return None

    # Create maxuser record with available fields
    maxuser_record = {field: record.get(field) for field in maxuser_fields if field in record}

    # Add personid reference
    maxuser_record['personid'] = personid

    # Add sync metadata
    maxuser_record['_last_sync'] = datetime.datetime.now().isoformat()
    maxuser_record['_sync_status'] = 'synced'

    return maxuser_record

def extract_groupuser_data(record, maxuserid):
    """Extract groupuser data from a normalized record."""
    groupuser_fields = [
        'groupuserid', 'groupname', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'groupuserid' not in record:
        logger.warning("Groupuser record missing groupuserid, skipping")
        return None

    # Create groupuser record with available fields
    groupuser_record = {field: record.get(field) for field in groupuser_fields if field in record}

    # Add maxuserid reference
    groupuser_record['maxuserid'] = maxuserid

    # Add sync metadata
    groupuser_record['_last_sync'] = datetime.datetime.now().isoformat()
    groupuser_record['_sync_status'] = 'synced'

    return groupuser_record

def extract_maxgroup_data(record):
    """Extract maxgroup data from a normalized record."""
    maxgroup_fields = [
        'maxgroupid', 'groupname', 'description', 'sidenav', 'authallsites',
        'authallstorerooms', 'authallgls', 'authlaborall', 'authlaborself',
        'authlaborcrew', 'authlaborsuper', 'authpersongroup', 'authallrepfacs',
        'nullrepfac', 'independent', 'pluspauthallcust', 'pluspauthcustvnd',
        'pluspauthgrplst', 'pluspauthperslst', 'pluspauthnoncust',
        'sctemplateid', '_rowstamp'
    ]

    # Check if we have the required fields
    if 'maxgroupid' not in record:
        logger.warning("Maxgroup record missing maxgroupid, skipping")
        return None

    # Create maxgroup record with available fields - exactly as received from Maximo
    maxgroup_record = {field: record.get(field) for field in maxgroup_fields if field in record}

    # Add sync metadata
    maxgroup_record['_last_sync'] = datetime.datetime.now().isoformat()
    maxgroup_record['_sync_status'] = 'synced'

    return maxgroup_record

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
        # Sync each table in the correct order (respecting foreign key constraints)
        sync_tables = [
            'person',
            'maxuser',
            'groupuser',
            'maxgroup',
            'groupuser_maxgroup',
            'person_site'
        ]

        # First, check if maxgroup table is empty
        cursor.execute("SELECT COUNT(*) FROM maxgroup")
        maxgroup_count = cursor.fetchone()[0]
        if maxgroup_count == 0 and 'maxgroup' in processed_data and processed_data['maxgroup']:
            logger.info("Maxgroup table is empty, syncing maxgroup records first")
            # Sync maxgroup records first
            for record in processed_data['maxgroup']:
                try:
                    placeholders = ", ".join(["?" for _ in record.keys()])
                    fields = ", ".join(record.keys())
                    cursor.execute(f"INSERT INTO maxgroup ({fields}) VALUES ({placeholders})", list(record.values()))
                    sync_results['inserted']['maxgroup'] += 1
                    sync_results['total']['maxgroup'] += 1
                except sqlite3.Error as e:
                    logger.error(f"Error syncing record to maxgroup table: {e}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors']['maxgroup'] += 1

        for table in sync_tables:
            if table not in processed_data or not processed_data[table]:
                logger.info(f"No data to sync for {table} table")
                continue

            logger.info(f"Syncing {len(processed_data[table])} records to {table} table")

            for record in processed_data[table]:
                sync_results['total'][table] += 1

                try:
                    # Check if record exists
                    if table == 'person':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE personid = ?", (record['personid'],))
                    elif table == 'maxuser':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE maxuserid = ?", (record['maxuserid'],))
                    elif table == 'groupuser':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE groupuserid = ?", (record['groupuserid'],))
                    elif table == 'maxgroup':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE maxgroupid = ?", (record['maxgroupid'],))
                    elif table == 'groupuser_maxgroup':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE groupuserid = ? AND maxgroupid = ?",
                                      (record['groupuserid'], record['maxgroupid']))
                    elif table == 'person_site':
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE personid = ? AND siteid = ?",
                                      (record['personid'], record['siteid']))

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = ""

                        if table == 'person':
                            where_clause = "WHERE personid = ?"
                            params = list(record.values()) + [record['personid']]
                        elif table == 'maxuser':
                            where_clause = "WHERE maxuserid = ?"
                            params = list(record.values()) + [record['maxuserid']]
                        elif table == 'groupuser':
                            where_clause = "WHERE groupuserid = ?"
                            params = list(record.values()) + [record['groupuserid']]
                        elif table == 'maxgroup':
                            where_clause = "WHERE maxgroupid = ?"
                            params = list(record.values()) + [record['maxgroupid']]
                        elif table == 'groupuser_maxgroup':
                            where_clause = "WHERE groupuserid = ? AND maxgroupid = ?"
                            params = list(record.values()) + [record['groupuserid'], record['maxgroupid']]
                        elif table == 'person_site':
                            where_clause = "WHERE personid = ? AND siteid = ?"
                            params = list(record.values()) + [record['personid'], record['siteid']]

                        cursor.execute(f"UPDATE {table} SET {set_clause} {where_clause}", params)
                        sync_results['updated'][table] += 1
                    else:
                        # Insert new record
                        placeholders = ", ".join(["?" for _ in record.keys()])
                        fields = ", ".join(record.keys())

                        cursor.execute(f"INSERT INTO {table} ({fields}) VALUES ({placeholders})", list(record.values()))
                        sync_results['inserted'][table] += 1

                except sqlite3.Error as e:
                    logger.error(f"Error syncing record to {table} table: {e}")
                    logger.error(f"Record: {json.dumps(record)}")
                    sync_results['errors'][table] += 1

        # Update sync_status table
        now = datetime.datetime.now().isoformat()

        # Get counts for each table
        total_count = sum(sync_results['total'].values())
        new_records = sum(sync_results['inserted'].values())
        updated_records = sum(sync_results['updated'].values())

        # Create a more informative message
        message = f"Existing records: {total_count - new_records}, Newly added: {new_records}, Updated: {updated_records}, Total: {total_count}"
        logger.info(message)

        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("MXAPIPERUSER", now, total_count, "success", message)
        )

        # Commit the changes
        conn.commit()
        logger.info("Sync completed successfully")

    except Exception as e:
        logger.error(f"Error syncing data to database: {e}")
        conn.rollback()

        # Update sync_status table with error
        try:
            now = datetime.datetime.now().isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
                ("MXAPIPERUSER", now, 0, "error", str(e))
            )
            conn.commit()
        except:
            pass

        sync_results = None
    finally:
        conn.close()

    return sync_results

def main():
    """Main function to synchronize MXAPIPERUSER data."""
    parser = argparse.ArgumentParser(description='Synchronize MXAPIPERUSER data to local database')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
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

    # Get last sync time if not forcing full sync
    last_sync = None
    if not args.force_full:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT last_sync FROM sync_status WHERE endpoint = 'MXAPIPERUSER'")
            result = cursor.fetchone()
            if result:
                last_sync = result[0]
                logger.info(f"Last sync time: {last_sync}")
            conn.close()
        except Exception as e:
            logger.warning(f"Error getting last sync time: {e}")

    # Fetch data from MXAPIPERUSER endpoint
    print("Fetching data from MXAPIPERUSER endpoint")
    logger.info("Fetching data from MXAPIPERUSER endpoint")
    peruser_data = fetch_peruser_data(last_sync, args.limit)

    if not peruser_data:
        logger.error("Failed to fetch data from MXAPIPERUSER endpoint")
        return

    # Process the data
    logger.info("Processing person data")
    processed_data = process_person_data(peruser_data)

    if not processed_data:
        logger.error("Failed to process person data")
        return

    # Sync to database
    logger.info(f"Syncing data to database: {db_path}")
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

    # Log the sync results
    logger.info(f"Total records processed: {sum(sync_results['total'].values())}")
    logger.info("Inserted records:")
    for table, count in sync_results['inserted'].items():
        logger.info(f"  {table}: {count}")
    logger.info("Updated records:")
    for table, count in sync_results['updated'].items():
        logger.info(f"  {table}: {count}")
    logger.info("Errors:")
    for table, count in sync_results['errors'].items():
        logger.info(f"  {table}: {count}")

    logger.info("Sync completed")

if __name__ == "__main__":
    main()
