#!/usr/bin/env python3
"""
Script to update the inventory-related tables schema in the Maximo offline database.
This script adds missing columns identified during sync operations.
"""
import os
import sys
import sqlite3
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('update_inventory_schema')

def update_inventory_schema(db_path):
    """
    Update the inventory-related tables schema in the SQLite database.

    Args:
        db_path (str): Path to the SQLite database file
    """
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if the tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_invcost'")
        if not cursor.fetchone():
            logger.error("Table inventory_invcost does not exist")
            return False

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_matrectrans'")
        if not cursor.fetchone():
            logger.error("Table inventory_matrectrans does not exist")
            return False

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_transfercuritem'")
        if not cursor.fetchone():
            logger.error("Table inventory_transfercuritem does not exist")
            return False

        # Add missing columns to inventory_invcost table
        logger.info("Adding missing columns to inventory_invcost table")
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(inventory_invcost)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'controlacc' not in columns:
                cursor.execute("ALTER TABLE inventory_invcost ADD COLUMN controlacc TEXT")
                logger.info("Added 'controlacc' column to inventory_invcost table")
        except sqlite3.Error as e:
            logger.error(f"Error adding columns to inventory_invcost table: {e}")
            return False

        # Add missing columns to inventory_matrectrans table
        logger.info("Adding missing columns to inventory_matrectrans table")
        try:
            # Check if columns exist
            cursor.execute("PRAGMA table_info(inventory_matrectrans)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'packingslipnum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN packingslipnum TEXT")
                logger.info("Added 'packingslipnum' column to inventory_matrectrans table")

            if 'invuselinenum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN invuselinenum INTEGER")
                logger.info("Added 'invuselinenum' column to inventory_matrectrans table")

            if 'statuschangeby' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN statuschangeby TEXT")
                logger.info("Added 'statuschangeby' column to inventory_matrectrans table")

            if 'invuselineid' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN invuselineid INTEGER")
                logger.info("Added 'invuselineid' column to inventory_matrectrans table")

            if 'proratecost' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN proratecost REAL")
                logger.info("Added 'proratecost' column to inventory_matrectrans table")

            if 'shipmentnum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN shipmentnum TEXT")
                logger.info("Added 'shipmentnum' column to inventory_matrectrans table")

            if 'shipmentlinenum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN shipmentlinenum TEXT")
                logger.info("Added 'shipmentlinenum' column to inventory_matrectrans table")

            if 'invuseid' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN invuseid INTEGER")
                logger.info("Added 'invuseid' column to inventory_matrectrans table")

            if 'mrlinenum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN mrlinenum INTEGER")
                logger.info("Added 'mrlinenum' column to inventory_matrectrans table")

            if 'mrnum' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN mrnum TEXT")
                logger.info("Added 'mrnum' column to inventory_matrectrans table")

            if 'issueto' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN issueto TEXT")
                logger.info("Added 'issueto' column to inventory_matrectrans table")

            if 'invuselinesplitid' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN invuselinesplitid INTEGER")
                logger.info("Added 'invuselinesplitid' column to inventory_matrectrans table")

            if 'statusdate' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN statusdate TEXT")
                logger.info("Added 'statusdate' column to inventory_matrectrans table")

            if 'requestedby' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN requestedby TEXT")
                logger.info("Added 'requestedby' column to inventory_matrectrans table")

            if 'qtyrequested' not in columns:
                cursor.execute("ALTER TABLE inventory_matrectrans ADD COLUMN qtyrequested REAL")
                logger.info("Added 'qtyrequested' column to inventory_matrectrans table")
        except sqlite3.Error as e:
            logger.error(f"Error adding columns to inventory_matrectrans table: {e}")
            return False

        # Add missing columns to inventory_transfercuritem table
        logger.info("Adding missing columns to inventory_transfercuritem table")
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(inventory_transfercuritem)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'glcreditacct' not in columns:
                cursor.execute("ALTER TABLE inventory_transfercuritem ADD COLUMN glcreditacct TEXT")
                logger.info("Added 'glcreditacct' column to inventory_transfercuritem table")
        except sqlite3.Error as e:
            logger.error(f"Error adding columns to inventory_transfercuritem table: {e}")
            return False

        # Commit the changes
        conn.commit()
        logger.info("Database schema updated successfully")
        return True

    except Exception as e:
        logger.error(f"Error updating database schema: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

def main():
    """Main function to update the inventory-related tables schema."""
    parser = argparse.ArgumentParser(description='Update inventory-related tables schema in Maximo offline database')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')

    args = parser.parse_args()

    # Expand the path
    db_path = os.path.expanduser(args.db_path)

    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return

    # Update the schema
    if update_inventory_schema(db_path):
        logger.info("Schema update completed successfully")
    else:
        logger.error("Schema update failed")

if __name__ == "__main__":
    main()
