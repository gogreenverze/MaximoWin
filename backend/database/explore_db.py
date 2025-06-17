#!/usr/bin/env python3
"""
Database Explorer for Maximo Offline Database.
This script provides a comprehensive interface to:
1. List all tables in the database
2. Show records from each table
3. Execute predefined SQL queries
4. Explore relationships between tables
"""
import os
import sys
import sqlite3
import logging
import argparse
import json
from pathlib import Path
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('explore_db')

# Default database path
DEFAULT_DB_PATH = '~/.maximo_offline/maximo.db'

# Predefined queries from query_relationships.sql
PREDEFINED_QUERIES = {
    "organization_details": """
        SELECT orgid, description, organizationid, active, basecurrency1 
        FROM organization 
        WHERE orgid = ?;
    """,
    "related_sites": """
        SELECT siteid, description, active, systemid
        FROM site 
        WHERE orgid = ?;
    """,
    "related_addresses": """
        SELECT addresscode, description, address1, address2, address5
        FROM address 
        WHERE orgid = ?;
    """,
    "billtoshipto_relationships": """
        SELECT 
            b.siteid, 
            s.description as site_description, 
            b.addresscode, 
            a.description as address_description,
            CASE WHEN b.billtodefault = 1 THEN 'Yes' ELSE 'No' END as default_billto,
            CASE WHEN b.shiptodefault = 1 THEN 'Yes' ELSE 'No' END as default_shipto
        FROM billtoshipto b
        JOIN site s ON b.siteid = s.siteid AND b.orgid = s.orgid
        JOIN address a ON b.addresscode = a.addresscode AND b.orgid = a.orgid
        WHERE b.orgid = ?
        ORDER BY b.siteid;
    """,
    "person_details": """
        SELECT personid, displayname, firstname, lastname, status, primaryemail
        FROM person
        WHERE personid = ?;
    """,
    "user_details": """
        SELECT u.userid, u.status, u.defsite, u.insertsite, p.displayname
        FROM maxuser u
        JOIN person p ON u.personid = p.personid
        WHERE u.userid = ?;
    """,
    "workorders_by_site": """
        SELECT wonum, description, status, assetnum, location, schedstart, schedfinish
        FROM workorders
        WHERE siteid = ?
        ORDER BY wonum;
    """,
    "assets_by_site": """
        SELECT assetnum, description, status, location
        FROM assets
        WHERE siteid = ?
        ORDER BY assetnum;
    """,
    "inventory_by_site": """
        SELECT itemnum, description, status, location, curbal
        FROM inventory
        WHERE siteid = ?
        ORDER BY itemnum;
    """
}

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

def execute_predefined_query(conn, query_name, param_value):
    """Execute a predefined query with a parameter."""
    if query_name not in PREDEFINED_QUERIES:
        print(f"Query '{query_name}' not found.")
        return
    
    query = PREDEFINED_QUERIES[query_name]
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, (param_value,))
        columns = [description[0] for description in cursor.description]
        records = cursor.fetchall()
        
        if not records:
            print(f"No results found for query '{query_name}' with parameter '{param_value}'.")
            return
        
        # Convert records to list of dictionaries for better display
        records_dict = []
        for record in records:
            record_dict = {}
            for i, column in enumerate(columns):
                record_dict[column] = record[i]
            records_dict.append(record_dict)
        
        # Display records in a table format
        print(f"\nResults for query '{query_name}' with parameter '{param_value}':")
        print(tabulate(records_dict, headers="keys", tablefmt="grid"))
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

def explore_database(db_path):
    """Main function to explore the database."""
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
        
        while True:
            print("\n=== Maximo Offline Database Explorer ===")
            print("1. List all tables")
            print("2. View table records")
            print("3. Execute predefined query")
            print("4. Exit")
            
            choice = input("\nEnter your choice (1-4): ")
            
            if choice == '1':
                print("\nTables in the database:")
                for i, table in enumerate(tables, 1):
                    record_count = get_record_count(conn, table)
                    print(f"{i}. {table} ({record_count} records)")
            
            elif choice == '2':
                print("\nTables in the database:")
                for i, table in enumerate(tables, 1):
                    record_count = get_record_count(conn, table)
                    print(f"{i}. {table} ({record_count} records)")
                
                table_choice = input("\nEnter table number to view (or 'b' to go back): ")
                if table_choice.lower() == 'b':
                    continue
                
                try:
                    table_index = int(table_choice) - 1
                    if 0 <= table_index < len(tables):
                        display_table_records(conn, tables[table_index])
                    else:
                        print(f"Invalid table number. Please enter a number between 1 and {len(tables)}.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            
            elif choice == '3':
                print("\nPredefined queries:")
                for i, query_name in enumerate(PREDEFINED_QUERIES.keys(), 1):
                    print(f"{i}. {query_name}")
                
                query_choice = input("\nEnter query number to execute (or 'b' to go back): ")
                if query_choice.lower() == 'b':
                    continue
                
                try:
                    query_index = int(query_choice) - 1
                    if 0 <= query_index < len(PREDEFINED_QUERIES):
                        query_name = list(PREDEFINED_QUERIES.keys())[query_index]
                        param_value = input(f"Enter parameter value for query '{query_name}': ")
                        execute_predefined_query(conn, query_name, param_value)
                    else:
                        print(f"Invalid query number. Please enter a number between 1 and {len(PREDEFINED_QUERIES)}.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            
            elif choice == '4':
                print("Exiting database explorer.")
                break
            
            else:
                print("Invalid choice. Please enter a number between 1 and 4.")
    
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Main function to run the database explorer."""
    parser = argparse.ArgumentParser(description='Explore the Maximo offline database')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help=f'Path to the SQLite database file (default: {DEFAULT_DB_PATH})')
    
    args = parser.parse_args()
    
    # Explore the database
    explore_database(args.db_path)

if __name__ == "__main__":
    main()
