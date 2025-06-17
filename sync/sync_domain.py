#!/usr/bin/env python3
"""
Script to synchronize domain data from MXAPIDOMAIN endpoint to local SQLite database.
This script will:
1. Load API key from .env file
2. Fetch data from MXAPIDOMAIN endpoint
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
logger = logging.getLogger('sync_domain')

# Load environment variables from .env file
load_dotenv()

# Get API key and base URL from environment variables
API_KEY = os.getenv('MAXIMO_API_KEY')
BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

def get_last_sync_time(db_path, endpoint="MXAPIDOMAIN"):
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

def fetch_domain_data(last_sync=None, limit=1000):
    """
    Fetch domain data from MXAPIDOMAIN endpoint.

    Args:
        last_sync (str): Last sync time in ISO format
        limit (int): Maximum number of records to fetch

    Returns:
        dict: JSON response from the API
    """
    endpoint = f"{BASE_URL}/api/os/mxapidomain"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": str(limit),
        "oslc.select": "*"  # Request all fields
    }

    # If we have a last sync time, don't use it in the query
    # The MXAPIDOMAIN endpoint doesn't support filtering by changedate
    # Just log that we're doing a full sync
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
        response = requests.get(
            endpoint,
            params=query_params,
            headers=headers,
            timeout=(3.05, 15)  # Connection timeout, read timeout
        )

        # Check for successful response
        if response.status_code == 200:
            logger.info(f"Successfully fetched domain data. Status code: {response.status_code}")

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
                    logger.error(f"No member data found in response. Keys: {list(data.keys())}")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text: {response.text[:500]}")
                return None
        else:
            logger.error(f"Error fetching domain data. Status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        logger.error(f"Exception during request: {str(e)}")
        return None

def normalize_record(record):
    """
    Normalize a domain record by removing prefixes and extracting nested data.

    Args:
        record (dict): Raw domain record from API

    Returns:
        dict: Normalized domain record
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

def extract_domain_values(record):
    """
    Extract domain values from a domain record.

    Args:
        record (dict): Normalized domain record

    Returns:
        list: List of domain value records
    """
    domain_values = []

    # Check for synonym domain values
    if 'synonymdomain' in record and isinstance(record['synonymdomain'], list):
        for synonym in record['synonymdomain']:
            # Normalize the synonym record
            norm_synonym = normalize_record(synonym)

            # Create domain value record
            domain_value = {
                'domainid': record['domainid'],
                'value': norm_synonym.get('value'),
                'description': norm_synonym.get('description'),
                'maxvalue': norm_synonym.get('maxvalue'),
                'defaults': 1 if norm_synonym.get('defaults') else 0,
                'internal': 0,  # Default to not internal
                '_rowstamp': norm_synonym.get('_rowstamp'),
                '_last_sync': datetime.datetime.now().isoformat(),
                '_sync_status': 'synced'
            }

            domain_values.append(domain_value)

    # Check for ALN domain values
    if 'alndomain' in record and isinstance(record['alndomain'], list):
        for aln in record['alndomain']:
            # Normalize the ALN record
            norm_aln = normalize_record(aln)

            # Create domain value record
            domain_value = {
                'domainid': record['domainid'],
                'value': norm_aln.get('value'),
                'description': norm_aln.get('description'),
                'maxvalue': None,
                'defaults': 0,  # Default to not default
                'internal': 0,  # Default to not internal
                '_rowstamp': norm_aln.get('_rowstamp'),
                '_last_sync': datetime.datetime.now().isoformat(),
                '_sync_status': 'synced'
            }

            domain_values.append(domain_value)

    # Check for numeric domain values
    if 'numericdomain' in record and isinstance(record['numericdomain'], list):
        for numeric in record['numericdomain']:
            # Normalize the numeric record
            norm_numeric = normalize_record(numeric)

            # Create domain value record
            domain_value = {
                'domainid': record['domainid'],
                'value': str(norm_numeric.get('value')),  # Convert numeric to string
                'description': norm_numeric.get('description'),
                'maxvalue': None,
                'defaults': 0,  # Default to not default
                'internal': 0,  # Default to not internal
                '_rowstamp': norm_numeric.get('_rowstamp'),
                '_last_sync': datetime.datetime.now().isoformat(),
                '_sync_status': 'synced'
            }

            domain_values.append(domain_value)

    return domain_values

def process_data(data):
    """
    Process and normalize the domain data.

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
        'domains': [],
        'domain_values': []
    }

    # Process each domain record
    for record in data['member']:
        # Normalize the record
        normalized = normalize_record(record)

        # Extract domain record
        domain_record = {
            'domainid': normalized.get('domainid'),
            'domaintype': normalized.get('domaintype'),
            'maxtype': normalized.get('maxtype'),
            'maxtype_description': normalized.get('maxtype_description'),
            'description': normalized.get('description'),
            'internal': normalized.get('internal', 0),
            'internal_description': normalized.get('internal_description'),
            'domaintype_description': normalized.get('domaintype_description'),
            'length': normalized.get('length'),
            'maxdomainid': normalized.get('maxdomainid'),
            'scale': normalized.get('scale'),
            'nevercache': 1 if normalized.get('nevercache') else 0,
            '_rowstamp': normalized.get('_rowstamp'),
            '_last_sync': datetime.datetime.now().isoformat(),
            '_sync_status': 'synced'
        }

        # Add to processed data
        processed_data['domains'].append(domain_record)

        # Extract domain values
        domain_values = extract_domain_values(normalized)
        processed_data['domain_values'].extend(domain_values)

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
            'domains',
            'domain_values'
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
                    if table == 'domains':
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE domainid = ?",
                            (record['domainid'],)
                        )
                    elif table == 'domain_values':
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE domainid = ? AND value = ?",
                            (record['domainid'], record['value'])
                        )

                    exists = cursor.fetchone()[0] > 0

                    if exists:
                        # Update existing record
                        set_clause = ", ".join([f"{field} = ?" for field in record.keys()])
                        where_clause = ""

                        if table == 'domains':
                            where_clause = "WHERE domainid = ?"
                            params = list(record.values()) + [record['domainid']]
                        elif table == 'domain_values':
                            where_clause = "WHERE domainid = ? AND value = ?"
                            params = list(record.values()) + [record['domainid'], record['value']]

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

        # Get counts for each table
        new_records = sum(sync_results['inserted'].values())
        updated_records = sum(sync_results['updated'].values())

        # Create a more informative message
        message = f"Existing records: {total_records - new_records}, Newly added: {new_records}, Updated: {updated_records}, Total: {total_records}"
        logger.info(message)

        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("MXAPIDOMAIN", now, total_records, "success", message)
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
    """Main function to fetch and sync domain data."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sync domain data from Maximo to local database')
    parser.add_argument('--db-path', default=DEFAULT_DB_PATH, help='Path to SQLite database')
    parser.add_argument('--force-full', action='store_true', help='Force full sync (ignore last sync time)')
    parser.add_argument('--limit', type=int, default=1000, help='Maximum number of records to fetch')
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

    # Fetch domain data
    domain_data = fetch_domain_data(last_sync, args.limit)

    if not domain_data:
        logger.error("Failed to fetch domain data")
        return

    # Process the data
    processed_data = process_data(domain_data)

    if not processed_data:
        logger.error("Failed to process domain data")
        return

    # Sync to database
    sync_results = sync_to_database(processed_data, args.db_path)

    if not sync_results:
        logger.error("Failed to sync domain data to database")
        return

    # Print sync results
    logger.info("Sync completed successfully")
    logger.info(f"Domains: {sync_results['inserted']['domains']} inserted, {sync_results['updated']['domains']} updated")
    logger.info(f"Domain values: {sync_results['inserted']['domain_values']} inserted, {sync_results['updated']['domain_values']} updated")
    logger.info(f"Total records processed: {sum(sync_results['total'].values())}")

if __name__ == "__main__":
    main()
