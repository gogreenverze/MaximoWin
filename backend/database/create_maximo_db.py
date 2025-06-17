#!/usr/bin/env python3
"""
Script to create a SQLite database for Maximo offline data.
This script will:
1. Create a SQLite database
2. Create tables for each Maximo API endpoint
3. Set up indexes for efficient querying
"""
import os
import sys
import sqlite3
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('create_maximo_db')

def create_database(db_path, schema_dir=None):
    """
    Create a SQLite database with tables for Maximo data.

    Args:
        db_path (str): Path to the SQLite database file
        schema_dir (str): Directory containing schema SQL files
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    logger.info(f"Creating database at {db_path}")

    try:
        # Create the organizations table
        logger.info("Creating organizations table")

        if schema_dir:
            # Use the schema file if available
            org_schema_path = os.path.join(schema_dir, 'organization_schema.sql')
            if os.path.exists(org_schema_path):
                with open(org_schema_path, 'r') as f:
                    org_schema = f.read()
                cursor.executescript(org_schema)
                logger.info(f"Created organizations table from schema file: {org_schema_path}")
            else:
                logger.warning(f"Schema file not found: {org_schema_path}")
                create_default_tables(cursor)

            # Create the users table
            logger.info("Creating users table")
            peruser_schema_path = os.path.join(schema_dir, 'peruser_schema.sql')
            if os.path.exists(peruser_schema_path):
                with open(peruser_schema_path, 'r') as f:
                    peruser_schema = f.read()
                cursor.executescript(peruser_schema)
                logger.info(f"Created users table from schema file: {peruser_schema_path}")
            else:
                logger.warning(f"Schema file not found: {peruser_schema_path}")
                create_default_user_tables(cursor)

            # Create the locations table
            logger.info("Creating locations table")
            locations_schema_path = os.path.join(schema_dir, 'locations_schema.sql')
            if os.path.exists(locations_schema_path):
                with open(locations_schema_path, 'r') as f:
                    locations_schema = f.read()
                cursor.executescript(locations_schema)
                logger.info(f"Created locations table from schema file: {locations_schema_path}")

            # Create the assets table
            logger.info("Creating assets table")
            assets_schema_path = os.path.join(schema_dir, 'assets_schema.sql')
            if os.path.exists(assets_schema_path):
                with open(assets_schema_path, 'r') as f:
                    assets_schema = f.read()
                cursor.executescript(assets_schema)
                logger.info(f"Created assets table from schema file: {assets_schema_path}")

            # Create the asset-related tables
            logger.info("Creating asset-related tables")
            asset_related_schema_path = os.path.join(schema_dir, 'asset_related_tables_schema.sql')
            if os.path.exists(asset_related_schema_path):
                with open(asset_related_schema_path, 'r') as f:
                    asset_related_schema = f.read()
                cursor.executescript(asset_related_schema)
                logger.info(f"Created asset-related tables from schema file: {asset_related_schema_path}")

            # Create the domain tables
            logger.info("Creating domain tables")
            domain_schema_path = os.path.join(schema_dir, 'domain_schema.sql')
            if os.path.exists(domain_schema_path):
                with open(domain_schema_path, 'r') as f:
                    domain_schema = f.read()
                cursor.executescript(domain_schema)
                logger.info(f"Created domain tables from schema file: {domain_schema_path}")

            # Create the work order tables
            logger.info("Creating work order tables")
            wodetail_schema_path = os.path.join(schema_dir, 'wodetail_schema.sql')
            if os.path.exists(wodetail_schema_path):
                with open(wodetail_schema_path, 'r') as f:
                    wodetail_schema = f.read()
                cursor.executescript(wodetail_schema)
                logger.info(f"Created work order tables from schema file: {wodetail_schema_path}")

        else:
            create_default_tables(cursor)
            create_default_user_tables(cursor)

        # Create a table to track sync status
        logger.info("Creating sync_status table")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_status (
            endpoint TEXT PRIMARY KEY,
            last_sync TIMESTAMP,
            record_count INTEGER,
            status TEXT,
            message TEXT
        );
        ''')

        # Commit the changes
        conn.commit()
        logger.info("Database created successfully")

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def create_default_tables(cursor):
    """Create default tables if schema files are not available."""
    # Organization table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS organization (
        orgid TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        organizationid INTEGER NOT NULL,
        active INTEGER NOT NULL,
        basecurrency1 TEXT NOT NULL,
        category TEXT NOT NULL,
        clearingacct TEXT,
        companysetid TEXT,
        dfltitemstatus TEXT,
        dfltitemstatus_description TEXT,
        enterby TEXT,
        enterdate TEXT,
        itemsetid TEXT,
        plusgaddassetspec INTEGER,
        plusgaddfailcode INTEGER,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT
    );
    ''')

    # Site table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS site (
        siteid TEXT NOT NULL,
        orgid TEXT NOT NULL,
        description TEXT,
        active INTEGER,
        systemid TEXT,
        siteuid INTEGER,
        vecfreight TEXT,
        contact TEXT,
        enterby TEXT,
        enterdate TEXT,
        changeby TEXT,
        changedate TEXT,
        plusgopenomuid INTEGER,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (siteid, orgid),
        FOREIGN KEY (orgid) REFERENCES organization(orgid)
    );
    ''')

    # Address table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS address (
        addressid INTEGER,
        addresscode TEXT NOT NULL,
        orgid TEXT NOT NULL,
        description TEXT,
        address1 TEXT,
        address2 TEXT,
        address3 TEXT,
        address4 TEXT,
        address5 TEXT,
        changeby TEXT,
        changedate TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (addresscode, orgid),
        FOREIGN KEY (orgid) REFERENCES organization(orgid)
    );
    ''')

    # BillToShipTo table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS billtoshipto (
        billtoshiptoid INTEGER,
        siteid TEXT NOT NULL,
        orgid TEXT NOT NULL,
        addresscode TEXT NOT NULL,
        billtodefault INTEGER,
        shiptodefault INTEGER,
        billto INTEGER,
        shipto INTEGER,
        billtocontact TEXT,
        shiptocontact TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (billtoshiptoid, siteid, orgid),
        FOREIGN KEY (siteid, orgid) REFERENCES site(siteid, orgid),
        FOREIGN KEY (addresscode, orgid) REFERENCES address(addresscode, orgid)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_organization_active ON organization(active);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_organization_organizationid ON organization(organizationid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_site_orgid ON site(orgid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_site_active ON site(active);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_address_orgid ON address(orgid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_billtoshipto_siteid_orgid ON billtoshipto(siteid, orgid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_billtoshipto_addresscode_orgid ON billtoshipto(addresscode, orgid);
    ''')

    logger.info("Created organization tables with default schema")

def create_default_user_tables(cursor):
    """Create default user tables if schema files are not available."""
    # Person table (MXAPIPERUSER)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS person (
        personid TEXT PRIMARY KEY,
        personuid INTEGER NOT NULL,
        displayname TEXT,
        firstname TEXT,
        lastname TEXT,
        title TEXT,
        status TEXT NOT NULL,
        status_description TEXT NOT NULL,
        statusdate TEXT NOT NULL,
        primaryemail TEXT,
        primaryphone TEXT,
        locationorg TEXT,
        locationsite TEXT,
        location TEXT,
        country TEXT,
        city TEXT,
        stateprovince TEXT,
        addressline1 TEXT,
        postalcode TEXT,
        department TEXT,
        supervisor TEXT,
        employeetype TEXT,
        employeetype_description TEXT,
        language TEXT,
        timezone TEXT,
        timezone_description TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT
    );
    ''')

    # Maxuser table (nested in MXAPIPERUSER.maxuser)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS maxuser (
        maxuserid INTEGER PRIMARY KEY,
        personid TEXT NOT NULL,
        userid TEXT NOT NULL,
        status TEXT NOT NULL,
        defsite TEXT,
        insertsite TEXT,
        querywithsite INTEGER,
        screenreader INTEGER,
        failedlogins INTEGER,
        sysuser INTEGER,
        type TEXT,
        type_description TEXT,
        loginid TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        FOREIGN KEY (personid) REFERENCES person(personid)
    );
    ''')

    # Groupuser table (nested in MXAPIPERUSER.maxuser.groupuser)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groupuser (
        groupuserid INTEGER PRIMARY KEY,
        maxuserid INTEGER NOT NULL,
        groupname TEXT NOT NULL,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        FOREIGN KEY (maxuserid) REFERENCES maxuser(maxuserid)
    );
    ''')

    # Maxgroup table (nested in MXAPIPERUSER.maxuser.groupuser.maxgroup)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS maxgroup (
        maxgroupid INTEGER PRIMARY KEY,
        groupname TEXT NOT NULL,
        description TEXT,
        sidenav INTEGER,
        authallsites INTEGER,
        authallstorerooms INTEGER,
        authallgls INTEGER,
        authlaborall INTEGER,
        authlaborself INTEGER,
        authlaborcrew INTEGER,
        authlaborsuper INTEGER,
        authpersongroup INTEGER,
        authallrepfacs INTEGER,
        nullrepfac INTEGER,
        independent INTEGER,
        pluspauthallcust INTEGER,
        pluspauthcustvnd INTEGER,
        pluspauthgrplst INTEGER,
        pluspauthperslst INTEGER,
        pluspauthnoncust INTEGER,
        sctemplateid INTEGER,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT
    );
    ''')

    # Groupuser to Maxgroup relationship table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS groupuser_maxgroup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        groupuserid INTEGER NOT NULL,
        maxgroupid INTEGER NOT NULL,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        FOREIGN KEY (groupuserid) REFERENCES groupuser(groupuserid),
        FOREIGN KEY (maxgroupid) REFERENCES maxgroup(maxgroupid),
        UNIQUE(groupuserid, maxgroupid)
    );
    ''')

    # Person_site table (for tracking which sites a person has access to)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS person_site (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        personid TEXT NOT NULL,
        siteid TEXT NOT NULL,
        isdefault INTEGER DEFAULT 0,
        isinsert INTEGER DEFAULT 0,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        FOREIGN KEY (personid) REFERENCES person(personid),
        UNIQUE(personid, siteid)
    );
    ''')

    # Create indexes
    # Person table indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_status ON person(status);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_displayname ON person(displayname);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_personuid ON person(personuid);')

    # Maxuser table indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxuser_personid ON maxuser(personid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxuser_userid ON maxuser(userid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxuser_status ON maxuser(status);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxuser_defsite ON maxuser(defsite);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxuser_insertsite ON maxuser(insertsite);')

    # Groupuser table indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groupuser_maxuserid ON groupuser(maxuserid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groupuser_groupname ON groupuser(groupname);')

    # Maxgroup table indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_maxgroup_groupname ON maxgroup(groupname);')

    # Groupuser_maxgroup table indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groupuser_maxgroup_groupuserid ON groupuser_maxgroup(groupuserid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groupuser_maxgroup_maxgroupid ON groupuser_maxgroup(maxgroupid);')

    # Person_site indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_site_personid ON person_site(personid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_site_siteid ON person_site(siteid);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_site_isdefault ON person_site(isdefault);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_site_isinsert ON person_site(isinsert);')

    logger.info("Created user tables with default schema")

    # Locations table (MXAPILOCATIONS)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS locations (
        location TEXT NOT NULL,
        siteid TEXT NOT NULL,
        description TEXT,
        status TEXT,
        type TEXT,
        glaccount TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (location, siteid)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_locations_status ON locations(status);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_locations_siteid ON locations(siteid);
    ''')

    logger.info("Created locations table with default schema")

    # Assets table (MXAPIASSET)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assets (
        assetnum TEXT NOT NULL,
        siteid TEXT NOT NULL,
        description TEXT,
        status TEXT,
        location TEXT,
        parent TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (assetnum, siteid)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_assets_siteid ON assets(siteid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location);
    ''')

    logger.info("Created assets table with default schema")

    # Domains table (MXDOMAIN)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS domains (
        domainid TEXT NOT NULL,
        value TEXT NOT NULL,
        description TEXT,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (domainid, value)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_domains_domainid ON domains(domainid);
    ''')

    logger.info("Created domains table with default schema")

    # Work orders table (MXAPIWODETAIL)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS workorders (
        wonum TEXT NOT NULL,
        siteid TEXT NOT NULL,
        description TEXT,
        status TEXT,
        assetnum TEXT,
        location TEXT,
        schedstart TEXT,
        schedfinish TEXT,
        historyflag INTEGER,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (wonum, siteid)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_workorders_status ON workorders(status);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_workorders_siteid ON workorders(siteid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_workorders_assetnum ON workorders(assetnum);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_workorders_location ON workorders(location);
    ''')

    logger.info("Created workorders table with default schema")

    # Inventory table (MXAPIINVENTORY)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        itemnum TEXT NOT NULL,
        siteid TEXT NOT NULL,
        location TEXT NOT NULL,
        description TEXT,
        status TEXT,
        curbal REAL,
        _rowstamp TEXT,
        _last_sync TIMESTAMP,
        _sync_status TEXT,
        PRIMARY KEY (itemnum, siteid, location)
    );
    ''')

    # Create indexes
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(status);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_inventory_siteid ON inventory(siteid);
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory(location);
    ''')

    logger.info("Created inventory table with default schema")

def main():
    """Main function to create the database."""
    parser = argparse.ArgumentParser(description='Create a SQLite database for Maximo offline data')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
    parser.add_argument('--schema-dir', type=str, default=None,
                        help='Directory containing schema SQL files')

    args = parser.parse_args()

    # Expand the path
    db_path = os.path.expanduser(args.db_path)

    # Create the database
    create_database(db_path, args.schema_dir)

if __name__ == "__main__":
    main()
