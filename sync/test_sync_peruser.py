#!/usr/bin/env python3
"""
Test script to check if the sync_peruser.py script is working correctly.
"""
import os
import sys
import sqlite3
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_sync_peruser')

# Load environment variables from .env file
load_dotenv()

def test_database_connection(db_path):
    """Test the database connection."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the database has the required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['person', 'maxuser', 'groupuser', 'maxgroup', 'groupuser_maxgroup', 'person_site']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            logger.error(f"Missing tables: {missing_tables}")
            return False
        
        logger.info(f"Database has all required tables: {required_tables}")
        
        # Check if the tables have any records
        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"Table {table} has {count} records")
        
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Error testing database connection: {e}")
        return False

def test_api_connection():
    """Test the API connection."""
    import requests
    
    # Get API key and base URL from environment variables
    API_KEY = os.getenv('MAXIMO_API_KEY')
    BASE_URL = os.getenv('MAXIMO_BASE_URL', 'https://vectrustst01.manage.v2x.maximotest.gov2x.com/maximo')
    
    # Ensure API key is available
    if not API_KEY:
        logger.error("MAXIMO_API_KEY not found in .env file")
        return False
    
    # Prepare API endpoint
    endpoint = f"{BASE_URL}/api/os/mxapiperuser"
    
    # Prepare query parameters
    query_params = {
        "lean": "0",  # Get full response
        "oslc.pageSize": "1",  # Just get one record
        "oslc.select": "*",  # Request all fields
        "oslc.where": "status=\"ACTIVE\""  # Filter for active users
    }
    
    # Prepare headers with API key
    headers = {
        "Accept": "application/json",
        "apikey": API_KEY  # Using the API key from .env
    }
    
    logger.info(f"Testing API connection to {endpoint}")
    logger.info(f"Using API key: {API_KEY}")
    
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
            logger.info(f"API connection successful. Status code: {response.status_code}")
            return True
        else:
            logger.error(f"API connection failed. Status code: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            return False
    
    except Exception as e:
        logger.error(f"Exception during API request: {str(e)}")
        return False

def main():
    """Main function to test the sync_peruser.py script."""
    parser = argparse.ArgumentParser(description='Test the sync_peruser.py script')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
    
    args = parser.parse_args()
    
    # Expand the path
    db_path = os.path.expanduser(args.db_path)
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    # Test database connection
    logger.info("Testing database connection")
    if test_database_connection(db_path):
        logger.info("Database connection test passed")
    else:
        logger.error("Database connection test failed")
    
    # Test API connection
    logger.info("Testing API connection")
    if test_api_connection():
        logger.info("API connection test passed")
    else:
        logger.error("API connection test failed")

if __name__ == "__main__":
    main()
