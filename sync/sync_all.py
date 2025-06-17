#!/usr/bin/env python3
"""
Master script to synchronize all Maximo data to the local database.
"""
import os
import sys
import sqlite3
import argparse
import logging
import datetime
from dotenv import load_dotenv

# Import individual sync modules
import sync_peruser
import sync_locations
import sync_assets
import sync_domain
import sync_wodetail
import sync_inventory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sync_all')

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

def get_default_site(db_path):
    """
    Get the user's default site from the local database.

    Args:
        db_path (str): Path to the SQLite database

    Returns:
        str: Default site ID, or None if not found
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get the current user's ID from the environment
        username = os.getenv('MAXIMO_USERNAME', '')

        if not username:
            logger.warning("MAXIMO_USERNAME not found in environment, using default site LCVKWT")
            return "LCVKWT"

        # Query the database for the user's default site
        cursor.execute("""
            SELECT ps.siteid
            FROM person p
            JOIN maxuser mu ON p.personid = mu.personid
            JOIN person_site ps ON p.personid = ps.personid
            WHERE mu.userid = ? AND ps.isdefault = 1
        """, (username,))

        result = cursor.fetchone()
        conn.close()

        if result:
            logger.info(f"Found default site {result[0]} for user {username}")
            return result[0]
        else:
            logger.warning(f"No default site found for user {username}, using default site LCVKWT")
            return "LCVKWT"

    except Exception as e:
        logger.error(f"Error getting default site: {e}")
        logger.warning("Using default site LCVKWT")
        return "LCVKWT"

def update_sync_status(db_path):
    """
    Update the overall sync status in the database.

    Args:
        db_path (str): Path to the SQLite database
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get the latest sync time for each endpoint
        cursor.execute("SELECT endpoint, last_sync, record_count FROM sync_status")
        results = cursor.fetchall()

        # Calculate overall stats
        total_records = sum(result[2] for result in results if result[2])
        endpoints_synced = len(results)

        # Get the earliest sync time (this is when the sync started)
        sync_times = [result[1] for result in results if result[1]]
        if sync_times:
            earliest_sync = min(sync_times)
        else:
            earliest_sync = datetime.datetime.now().isoformat()

        # Update the overall sync status
        cursor.execute(
            "INSERT OR REPLACE INTO sync_status (endpoint, last_sync, record_count, status, message) VALUES (?, ?, ?, ?, ?)",
            ("ALL", earliest_sync, total_records, "success", f"Synced {endpoints_synced} endpoints with {total_records} total records")
        )

        conn.commit()
        conn.close()

        logger.info(f"Updated overall sync status: {endpoints_synced} endpoints, {total_records} total records")

    except Exception as e:
        logger.error(f"Error updating overall sync status: {e}")

def main():
    """Main function to synchronize all Maximo data."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Synchronize all Maximo data')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help='Path to the SQLite database file')
    parser.add_argument('--force-full', action='store_true',
                        help='Force a full sync instead of incremental')
    parser.add_argument('--endpoints', type=str, nargs='+',
                        choices=['peruser', 'locations', 'assets', 'domain', 'wodetail', 'inventory', 'all'],
                        default=['all'],
                        help='Specific endpoints to sync (default: all)')
    args = parser.parse_args()

    # Expand the database path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        logger.error("Please run create_maximo_db.py first")
        return

    # Get user's default site
    default_site = get_default_site(db_path)
    logger.info(f"Using default site: {default_site}")

    # Determine which endpoints to sync
    endpoints_to_sync = []
    if 'all' in args.endpoints:
        endpoints_to_sync = ['peruser', 'locations', 'assets', 'domain', 'wodetail', 'inventory']
    else:
        endpoints_to_sync = args.endpoints

    logger.info(f"Syncing endpoints: {', '.join(endpoints_to_sync)}")

    # Sync each endpoint using a safe approach that handles different function signatures
    def run_sync_module(module, module_name, args_list):
        """Run a sync module safely, handling different function signatures."""
        logger.info(f"Syncing {module_name} endpoint")
        try:
            # First try to call with args directly
            try:
                module.main(args_list)
                return True
            except TypeError as e:
                logger.info(f"main() doesn't accept arguments directly, trying with sys.argv: {e}")

                # If that fails, try with sys.argv
                original_argv = sys.argv
                try:
                    # Create new argv with our arguments
                    sys.argv = [f'sync_{module_name}.py'] + args_list

                    # Call main with no arguments
                    module.main()
                    return True
                except Exception as e2:
                    logger.error(f"Error running {module_name} sync: {e2}")
                    return False
                finally:
                    # Restore original argv
                    sys.argv = original_argv
        except Exception as e:
            logger.error(f"Error running {module_name} sync: {e}")
            return False

    # Process each endpoint
    if 'peruser' in endpoints_to_sync:
        run_sync_module(
            sync_peruser,
            "MXAPIPERUSER",
            ['--db-path', db_path] + (['--force-full'] if args.force_full else [])
        )

    if 'locations' in endpoints_to_sync:
        run_sync_module(
            sync_locations,
            "MXAPILOCATIONS",
            ['--db-path', db_path, '--site', default_site] + (['--force-full'] if args.force_full else [])
        )

    if 'assets' in endpoints_to_sync:
        run_sync_module(
            sync_assets,
            "MXAPIASSET",
            ['--db-path', db_path, '--site', default_site] + (['--force-full'] if args.force_full else [])
        )

    if 'domain' in endpoints_to_sync:
        run_sync_module(
            sync_domain,
            "MXAPIDOMAIN",
            ['--db-path', db_path] + (['--force-full'] if args.force_full else [])
        )

    if 'wodetail' in endpoints_to_sync:
        run_sync_module(
            sync_wodetail,
            "MXAPIWODETAIL",
            ['--db-path', db_path, '--site', default_site] + (['--force-full'] if args.force_full else [])
        )

    if 'inventory' in endpoints_to_sync:
        run_sync_module(
            sync_inventory,
            "MXAPIINVENTORY",
            ['--db-path', db_path, '--site', default_site] + (['--force-full'] if args.force_full else [])
        )

    # Update overall sync status
    update_sync_status(db_path)

    logger.info("All data synchronized successfully!")

if __name__ == "__main__":
    main()
