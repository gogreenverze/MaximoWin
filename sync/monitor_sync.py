#!/usr/bin/env python3
"""
Monitor script for Maximo sync operations.
This script monitors the sync_status table in the Maximo offline database
and displays the status of sync operations in real-time.
"""
import os
import sys
import time
import sqlite3
import argparse
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('monitor_sync')

# Default database path
DEFAULT_DB_PATH = os.path.expanduser('~/.maximo_offline/maximo.db')

def get_sync_status(db_path):
    """
    Get the current sync status from the database.

    Args:
        db_path (str): Path to the SQLite database

    Returns:
        list: List of sync status records
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query the sync_status table
        cursor.execute("""
            SELECT endpoint, last_sync, record_count, status, message
            FROM sync_status
            ORDER BY last_sync DESC
        """)
        results = cursor.fetchall()

        # Close the connection
        conn.close()

        return results
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return []

def get_table_counts(db_path):
    """
    Get record counts for all tables in the database.

    Args:
        db_path (str): Path to the SQLite database

    Returns:
        dict: Dictionary of table names and record counts
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        # Get record count for each table
        counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            counts[table] = count

        # Close the connection
        conn.close()

        return counts
    except Exception as e:
        logger.error(f"Error getting table counts: {e}")
        return {}

def format_timestamp(timestamp):
    """Format a timestamp for display."""
    if not timestamp:
        return "Never"

    try:
        dt = datetime.datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp

def monitor_sync(db_path, refresh_interval=5):
    """
    Monitor sync operations in real-time.

    Args:
        db_path (str): Path to the SQLite database
        refresh_interval (int): Refresh interval in seconds
    """
    try:
        while True:
            # Clear the screen
            os.system('cls' if os.name == 'nt' else 'clear')

            # Get sync status
            sync_status = get_sync_status(db_path)

            # Get table counts
            table_counts = get_table_counts(db_path)

            # Display header
            print(f"{Fore.CYAN}===== MAXIMO SYNC MONITOR ====={Style.RESET_ALL}")
            print(f"Database: {db_path}")
            print(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()

            # Display sync status
            if sync_status:
                status_data = []
                for endpoint, last_sync, record_count, status, message in sync_status:
                    # Format status with color
                    if status == "success":
                        status_formatted = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
                    elif status == "error":
                        status_formatted = f"{Fore.RED}{status}{Style.RESET_ALL}"
                    else:
                        status_formatted = f"{Fore.YELLOW}{status}{Style.RESET_ALL}"

                    status_data.append([
                        endpoint,
                        format_timestamp(last_sync),
                        record_count,
                        status_formatted,
                        message
                    ])

                print(f"{Fore.CYAN}Sync Status:{Style.RESET_ALL}")
                print(tabulate(
                    status_data,
                    headers=["Endpoint", "Last Sync", "Record Count", "Status", "Message"],
                    tablefmt="pretty"
                ))
            else:
                print(f"{Fore.YELLOW}No sync status records found{Style.RESET_ALL}")

            print()

            # Display table counts
            if table_counts:
                # Group tables by category
                categories = {
                    "User & Profile": ["person", "maxuser", "groupuser", "maxgroup", "groupuser_maxgroup", "person_site"],
                    "Locations": ["locations"],
                    "Assets": ["asset", "assetmeter", "assetspec"],
                    "Work Orders": ["workorder", "woactivity", "wplabor", "wpmaterial", "wptool"],
                    "Inventory": ["inventory", "inventory_invbalances", "inventory_invcost", "inventory_itemcondition",
                                 "inventory_matrectrans", "inventory_transfercuritem"],
                    "Domain": ["maxdomain", "alndomain"],
                    "System": ["sync_status"]
                }

                print(f"{Fore.CYAN}Table Record Counts:{Style.RESET_ALL}")

                for category, tables in categories.items():
                    category_data = []
                    for table in tables:
                        if table in table_counts:
                            category_data.append([table, table_counts[table]])

                    if category_data:
                        print(f"\n{Fore.YELLOW}{category}:{Style.RESET_ALL}")
                        print(tabulate(
                            category_data,
                            headers=["Table", "Record Count"],
                            tablefmt="simple"
                        ))

                # Show uncategorized tables
                all_category_tables = [table for tables in categories.values() for table in tables]
                uncategorized = [(table, count) for table, count in table_counts.items() if table not in all_category_tables]

                if uncategorized:
                    print(f"\n{Fore.YELLOW}Other Tables:{Style.RESET_ALL}")
                    print(tabulate(
                        uncategorized,
                        headers=["Table", "Record Count"],
                        tablefmt="simple"
                    ))
            else:
                print(f"{Fore.YELLOW}No tables found in the database{Style.RESET_ALL}")

            print(f"\n{Fore.CYAN}Press Ctrl+C to exit{Style.RESET_ALL}")

            # Wait for refresh interval
            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped")
    except Exception as e:
        logger.error(f"Error monitoring sync: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Monitor Maximo sync operations')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help='Path to the SQLite database file')
    parser.add_argument('--refresh', type=int, default=5,
                        help='Refresh interval in seconds')

    args = parser.parse_args()

    # Expand the path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return

    # Monitor sync operations
    monitor_sync(db_path, args.refresh)

if __name__ == "__main__":
    main()
