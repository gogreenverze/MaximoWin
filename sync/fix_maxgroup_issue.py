#!/usr/bin/env python3
"""
Script to fix the foreign key constraint issue in the Maximo offline database.
This script will:
1. Check if the maxgroup table is empty
2. If it is, create placeholder maxgroup records for all maxgroupid values in the groupuser_maxgroup table
3. This will allow the sync_peruser.py script to run without foreign key constraint errors
"""
import os
import sys
import sqlite3
import logging
import argparse
import datetime
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fix_maxgroup_issue')

def fetch_maxgroup_data():
    """
    Fetch maxgroup data from the Maximo API.

    Returns:
        list: List of maxgroup records
    """
    # Get API key and base URL from environment variables
    API_KEY = os.getenv('MAXIMO_API_KEY')
    BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')

    if not API_KEY:
        logger.error("MAXIMO_API_KEY not found in .env file")
        return []

    # Prepare API endpoint
    endpoint = f"{BASE_URL}/api/os/mxapimaxgroup"

    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": "100",  # Get up to 100 records
        "oslc.select": "*",  # Request all fields
    }

    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY  # Using the API key from .env
    }

    logger.info(f"Fetching maxgroup data from {endpoint}")

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
            data = response.json()

            if 'member' in data:
                maxgroup_records = []

                for member in data['member']:
                    maxgroup_record = {
                        'maxgroupid': member.get('maxgroupid'),
                        'groupname': member.get('groupname'),
                        'description': member.get('description'),
                        '_last_sync': datetime.datetime.now().isoformat(),
                        '_sync_status': 'synced'
                    }
                    maxgroup_records.append(maxgroup_record)

                logger.info(f"Successfully fetched {len(maxgroup_records)} maxgroup records")
                return maxgroup_records
            else:
                logger.error("No 'member' field in API response")
                return []
        else:
            logger.error(f"API request failed with status code {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return []

    except Exception as e:
        logger.error(f"Exception during API request: {str(e)}")
        return []

def fix_maxgroup_issue(db_path):
    """
    Fix the foreign key constraint issue in the Maximo offline database.

    Args:
        db_path (str): Path to the SQLite database file

    Returns:
        bool: True if successful, False otherwise
    """
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if maxgroup table is empty
        cursor.execute("SELECT COUNT(*) FROM maxgroup")
        maxgroup_count = cursor.fetchone()[0]

        if maxgroup_count > 0:
            logger.info(f"Maxgroup table already has {maxgroup_count} records, no fix needed")
            return True

        # Fetch maxgroup data from the API
        logger.info("Fetching maxgroup data from the API")
        maxgroup_records = fetch_maxgroup_data()

        if not maxgroup_records:
            logger.warning("No maxgroup records fetched from the API, falling back to placeholder records")

            # Get all unique maxgroupid values from groupuser_maxgroup table
            cursor.execute("SELECT DISTINCT maxgroupid FROM groupuser_maxgroup")
            maxgroupids = [row[0] for row in cursor.fetchall()]

            # Also check the groupuser table for maxgroup references
            try:
                # Check if the groupuser table has a maxgroupid column
                cursor.execute("PRAGMA table_info(groupuser)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'maxgroupid' in columns:
                    cursor.execute("SELECT DISTINCT maxgroupid FROM groupuser WHERE maxgroupid IS NOT NULL")
                    maxgroupids_from_groupuser = [row[0] for row in cursor.fetchall()]
                else:
                    logger.info("Groupuser table does not have a maxgroupid column")
                    maxgroupids_from_groupuser = []
            except sqlite3.Error as e:
                logger.error(f"Error getting maxgroupids from groupuser table: {e}")
                maxgroupids_from_groupuser = []

            # Combine the lists and remove duplicates
            all_maxgroupids = list(set(maxgroupids + maxgroupids_from_groupuser))

            if not all_maxgroupids:
                logger.info("No maxgroupid values found in groupuser_maxgroup or groupuser tables")
                # Create some default maxgroup records to ensure the sync works
                all_maxgroupids = [6, 7, 35, 37, 42, 43, 53, 56, 57, 69, 70, 128, 136, 161, 165, 205]
                logger.info(f"Using default maxgroupid values: {all_maxgroupids}")

            logger.info(f"Creating {len(all_maxgroupids)} placeholder maxgroup records")

            # Create placeholder maxgroup records for each maxgroupid
            for maxgroupid in all_maxgroupids:
                placeholder_record = {
                    'maxgroupid': maxgroupid,
                    'groupname': f"Group {maxgroupid}",  # Placeholder name
                    'description': f"Auto-created placeholder for maxgroupid {maxgroupid}",
                    '_last_sync': datetime.datetime.now().isoformat(),
                    '_sync_status': 'placeholder'
                }

                try:
                    placeholders = ", ".join(["?" for _ in placeholder_record.keys()])
                    fields = ", ".join(placeholder_record.keys())
                    cursor.execute(f"INSERT INTO maxgroup ({fields}) VALUES ({placeholders})",
                                  list(placeholder_record.values()))
                    logger.info(f"Successfully created placeholder maxgroup record for maxgroupid {maxgroupid}")
                except sqlite3.Error as e:
                    logger.error(f"Error creating placeholder maxgroup record for maxgroupid {maxgroupid}: {e}")
                    logger.error(f"Record: {json.dumps(placeholder_record)}")
                    continue
        else:
            # Insert the maxgroup records from the API
            logger.info(f"Inserting {len(maxgroup_records)} maxgroup records from the API")

            for record in maxgroup_records:
                try:
                    placeholders = ", ".join(["?" for _ in record.keys()])
                    fields = ", ".join(record.keys())
                    cursor.execute(f"INSERT INTO maxgroup ({fields}) VALUES ({placeholders})",
                                  list(record.values()))
                    logger.info(f"Successfully inserted maxgroup record for maxgroupid {record['maxgroupid']}")
                except sqlite3.Error as e:
                    logger.error(f"Error inserting maxgroup record for maxgroupid {record['maxgroupid']}: {e}")
                    logger.error(f"Record: {json.dumps(record)}")
                    continue

        # Commit the changes
        conn.commit()
        logger.info("Successfully fixed maxgroup issue")
        return True

    except Exception as e:
        logger.error(f"Error fixing maxgroup issue: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

def main():
    """Main function to fix the maxgroup issue."""
    parser = argparse.ArgumentParser(description='Fix the maxgroup issue in the Maximo offline database')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')

    args = parser.parse_args()

    # Expand the path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return

    # Fix the maxgroup issue
    if fix_maxgroup_issue(db_path):
        logger.info("Maxgroup issue fixed successfully")
    else:
        logger.error("Failed to fix maxgroup issue")

if __name__ == "__main__":
    main()
