#!/usr/bin/env python3
"""
Simple monitor script for Maximo sync operations.
This script displays the current status of sync operations from the database.
"""
import os
import sys
import sqlite3
import argparse
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('simple_monitor')

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

def display_sync_status(db_path):
    """
    Display the current sync status.
    
    Args:
        db_path (str): Path to the SQLite database
    """
    try:
        # Get sync status
        sync_status = get_sync_status(db_path)
        
        # Get table counts
        table_counts = get_table_counts(db_path)
        
        # Display header
        print("===== MAXIMO SYNC STATUS =====")
        print(f"Database: {db_path}")
        print(f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Display sync status
        if sync_status:
            print("Sync Status:")
            print("-" * 80)
            print(f"{'Endpoint':<15} {'Last Sync':<20} {'Records':<10} {'Status':<10} {'Message'}")
            print("-" * 80)
            
            for endpoint, last_sync, record_count, status, message in sync_status:
                print(f"{endpoint:<15} {format_timestamp(last_sync):<20} {record_count:<10} {status:<10} {message}")
        else:
            print("No sync status records found")
        
        print()
        
        # Display table counts
        if table_counts:
            print("Table Record Counts:")
            print("-" * 40)
            print(f"{'Table':<30} {'Record Count'}")
            print("-" * 40)
            
            # Sort tables by name
            for table in sorted(table_counts.keys()):
                print(f"{table:<30} {table_counts[table]}")
        else:
            print("No tables found in the database")
    
    except Exception as e:
        logger.error(f"Error displaying sync status: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Display Maximo sync status')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help='Path to the SQLite database file')
    
    args = parser.parse_args()
    
    # Expand the path
    db_path = os.path.expanduser(args.db_path)
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    # Display sync status
    display_sync_status(db_path)

if __name__ == "__main__":
    main()
