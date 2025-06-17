#!/usr/bin/env python3
"""
Script to query and display all records from each table in the Maximo offline database.
This script will:
1. Connect to the SQLite database
2. Get a list of all tables
3. Query each table and display all records
"""
import os
import sys
import sqlite3
import logging
import argparse
import json
from tabulate import tabulate
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('query_all_tables')

def get_all_tables(conn):
    """Get a list of all tables in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    return [table[0] for table in tables]

def get_table_columns(conn, table_name):
    """Get a list of columns for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    return [column[1] for column in columns]

def get_table_records(conn, table_name, limit=None, offset=0):
    """Get all records from a table with optional limit and offset."""
    cursor = conn.cursor()
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    cursor.execute(query)
    records = cursor.fetchall()
    return records

def get_record_count(conn, table_name):
    """Get the total number of records in a table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    return count

def display_table_records(conn, table_name, page_size=10):
    """Display all records from a table with pagination."""
    columns = get_table_columns(conn, table_name)
    total_records = get_record_count(conn, table_name)
    
    if total_records == 0:
        print(f"\nTable '{table_name}' is empty.")
        return
    
    print(f"\nTable: {table_name}")
    print(f"Total records: {total_records}")
    
    offset = 0
    while offset < total_records:
        records = get_table_records(conn, table_name, limit=page_size, offset=offset)
        
        # Convert records to list of dictionaries for better display
        records_dict = []
        for record in records:
            record_dict = {}
            for i, column in enumerate(columns):
                record_dict[column] = record[i]
            records_dict.append(record_dict)
        
        # Display records in a table format
        print(tabulate(records_dict, headers="keys", tablefmt="grid"))
        
        offset += page_size
        
        if offset < total_records:
            user_input = input(f"Showing records {offset-page_size+1}-{min(offset, total_records)} of {total_records}. Press Enter to continue, 'q' to quit this table: ")
            if user_input.lower() == 'q':
                break
        else:
            print(f"Showing records {offset-page_size+1}-{total_records} of {total_records}.")

def query_all_tables(db_path):
    """Query and display all records from each table in the database."""
    # Expand the path
    db_path = os.path.expanduser(db_path)
    
    # Check if the database file exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        
        # Get all tables
        tables = get_all_tables(conn)
        
        if not tables:
            logger.error("No tables found in the database.")
            return
        
        print(f"Found {len(tables)} tables in the database:")
        for i, table in enumerate(tables, 1):
            print(f"{i}. {table}")
        
        while True:
            try:
                user_input = input("\nEnter table number to view (or 'all' to view all tables, 'q' to quit): ")
                
                if user_input.lower() == 'q':
                    break
                
                if user_input.lower() == 'all':
                    for table in tables:
                        display_table_records(conn, table)
                        user_input = input("\nPress Enter to continue to the next table, 'q' to quit: ")
                        if user_input.lower() == 'q':
                            break
                    break
                
                table_index = int(user_input) - 1
                if 0 <= table_index < len(tables):
                    display_table_records(conn, tables[table_index])
                else:
                    print(f"Invalid table number. Please enter a number between 1 and {len(tables)}.")
            except ValueError:
                print("Invalid input. Please enter a number or 'all' or 'q'.")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                break
    
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Main function to query all tables."""
    parser = argparse.ArgumentParser(description='Query and display all records from each table in the Maximo offline database')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
    
    args = parser.parse_args()
    
    # Query all tables
    query_all_tables(args.db_path)

if __name__ == "__main__":
    main()
