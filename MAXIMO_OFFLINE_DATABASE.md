# Maximo Offline Database Implementation Guide

## End Goal
Create a robust offline database for Maximo that allows users to:
1. Download and store essential Maximo data locally
2. Access this data when offline
3. Make changes offline that sync when connection is restored
4. Filter data based on user's default site for efficiency

## Data Requirements

The following Maximo API endpoints need to be stored offline:

1. **MXAPIORGANIZATION** (ALL records)
2. **MXAPIPERUSER** (Only ACTIVE status)
3. **MXAPILOCATIONS** (OPERATING status, filtered by user's default site)
4. **MXAPIASSET** (OPERATING status, filtered by user's default site)
5. **MXDOMAIN** (ALL records)
6. **MXAPIWODETAIL** (Not CANCELED or CLOSED, not historical, filtered by user's default site)
7. **MXAPIINVENTORY** (ACTIVE status, filtered by user's default site)

## Authentication Strategy
- Use `.env` stored API key for all download operations
- Retain OAuth via token_manager for upload operations only
- No temporary API key generation

## Current Progress

### Completed
1. **Database Schema Design**
   - Created SQLite schema for organization-related tables (`organization`, `site`, `address`, `billtoshipto`)
   - Created SQLite schema for person-related tables (`person`, `maxuser`, `groupuser`, `maxgroup`, `person_site`)
   - Created SQLite schema for location-related tables
   - Created SQLite schema for asset-related tables
   - Created SQLite schema for domain-related tables (`domains`, `domain_values`)
   - Created SQLite schema for work order-related tables (`workorder`, `woserviceaddress`, `wolabor`, `womaterial`, `wotool`)
   - Implemented proper relationships between tables with foreign keys
   - Added indexes for efficient querying

2. **Database Creation**
   - Implemented `create_maximo_db.py` script to create the SQLite database
   - Added support for loading schema from SQL files or using default schemas

3. **MXAPIPERUSER Synchronization**
   - Implemented `sync_peruser.py` script to fetch and sync person data
   - Added support for incremental sync using last sync timestamp
   - Successfully synced 500 person records, 498 maxuser records, 3,447 groupuser records, and 477 person_site records

4. **MXAPILOCATIONS Synchronization**
   - Implemented `sync_locations.py` script to fetch and sync location data
   - Added filtering by site ID

5. **MXAPIASSET Synchronization**
   - Implemented `sync_assets.py` script to fetch and sync asset data
   - Added filtering by site ID and status

6. **MXAPIDOMAIN Synchronization**
   - Implemented `sync_domain.py` script to fetch and sync domain data
   - Successfully synced domain records and domain values

7. **MXAPIWODETAIL Synchronization**
   - Implemented `sync_wodetail.py` script to fetch and sync work order data
   - Added filtering by site ID (LCVIRQ) and status (WAPPR, APPR, INPRG, ASSIGN, WMATL)
   - Successfully synced 400+ work order records with related service address data
   - Implemented multi-status fetching to handle API limitations

### Remaining Endpoints to Implement
1. ~~**MXAPILOCATIONS** (Status="OPERATING" and siteid=loggedin user maxuser.defsite)~~ ✅ COMPLETED
2. ~~**MXAPIASSET** (status="OPERATING" and siteid=loggedin user maxuser.defsite)~~ ✅ COMPLETED
3. ~~**MXAPIDOMAIN** (all records)~~ ✅ COMPLETED
4. ~~**MXAPIWODETAIL** (status not in ("CAN","CLOSE") and historyflag=0 and siteid=loggedin user maxuser.defsite)~~ ✅ COMPLETED
5. **MXAPIINVENTORY** (STATUS="ACTIVE" and siteid=loggedin user maxuser.defsite)

## Database Schema

### Organization-related Tables
```sql
-- Main organization table
CREATE TABLE IF NOT EXISTS organization (
    orgid TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    -- Additional fields...
);

-- Site table
CREATE TABLE IF NOT EXISTS site (
    siteid TEXT NOT NULL,
    orgid TEXT NOT NULL,
    description TEXT,
    -- Additional fields...
    PRIMARY KEY (siteid, orgid),
    FOREIGN KEY (orgid) REFERENCES organization(orgid)
);

-- Address table
CREATE TABLE IF NOT EXISTS address (
    addresscode TEXT NOT NULL,
    orgid TEXT NOT NULL,
    -- Additional fields...
    PRIMARY KEY (addresscode, orgid),
    FOREIGN KEY (orgid) REFERENCES organization(orgid)
);

-- BillToShipTo table
CREATE TABLE IF NOT EXISTS billtoshipto (
    billtoshiptoid INTEGER,
    siteid TEXT NOT NULL,
    orgid TEXT NOT NULL,
    addresscode TEXT NOT NULL,
    -- Additional fields...
    PRIMARY KEY (billtoshiptoid, siteid, orgid),
    FOREIGN KEY (siteid, orgid) REFERENCES site(siteid, orgid),
    FOREIGN KEY (addresscode, orgid) REFERENCES address(addresscode, orgid)
);
```

### Person-related Tables
```sql
-- Person table
CREATE TABLE IF NOT EXISTS person (
    personid TEXT PRIMARY KEY,
    personuid INTEGER NOT NULL,
    displayname TEXT,
    -- Additional fields...
);

-- Maxuser table
CREATE TABLE IF NOT EXISTS maxuser (
    maxuserid INTEGER PRIMARY KEY,
    personid TEXT NOT NULL,
    userid TEXT NOT NULL,
    -- Additional fields...
    FOREIGN KEY (personid) REFERENCES person(personid)
);

-- Groupuser table
CREATE TABLE IF NOT EXISTS groupuser (
    groupuserid INTEGER PRIMARY KEY,
    maxuserid INTEGER NOT NULL,
    groupname TEXT NOT NULL,
    -- Additional fields...
    FOREIGN KEY (maxuserid) REFERENCES maxuser(maxuserid)
);

-- Maxgroup table
CREATE TABLE IF NOT EXISTS maxgroup (
    maxgroupid INTEGER PRIMARY KEY,
    groupname TEXT NOT NULL,
    description TEXT,
    -- Additional fields...
);

-- Person_site table
CREATE TABLE IF NOT EXISTS person_site (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    personid TEXT NOT NULL,
    siteid TEXT NOT NULL,
    isdefault INTEGER DEFAULT 0,
    isinsert INTEGER DEFAULT 0,
    -- Additional fields...
    FOREIGN KEY (personid) REFERENCES person(personid),
    UNIQUE(personid, siteid)
);
```

### Domain Tables
```sql
-- Main domains table
CREATE TABLE IF NOT EXISTS domains (
    domainid TEXT NOT NULL,
    domaintype TEXT NOT NULL,
    maxtype TEXT,
    maxtype_description TEXT,
    description TEXT,
    internal INTEGER NOT NULL,
    internal_description TEXT NOT NULL,
    domaintype_description TEXT NOT NULL,
    length INTEGER,
    maxdomainid INTEGER NOT NULL,
    scale INTEGER,
    nevercache INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (domainid)
);

-- Domain values table
CREATE TABLE IF NOT EXISTS domain_values (
    domainid TEXT NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    maxvalue TEXT,
    defaults INTEGER,
    internal INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (domainid, value),
    FOREIGN KEY (domainid) REFERENCES domains(domainid)
);
```

### Work Order Tables
```sql
-- Main workorder table
CREATE TABLE IF NOT EXISTS workorder (
    wonum TEXT NOT NULL,
    workorderid INTEGER NOT NULL,
    description TEXT,
    status TEXT NOT NULL,
    status_description TEXT,
    siteid TEXT NOT NULL,
    orgid TEXT NOT NULL,
    location TEXT,
    assetnum TEXT,
    parent TEXT,
    woclass TEXT,
    woclass_description TEXT,
    worktype TEXT,
    wopriority INTEGER,
    wopriority_description TEXT,
    reportedby TEXT,
    reportdate TEXT,
    createdby TEXT,
    createdate TEXT,
    changedate TEXT,
    changeby TEXT,
    owner TEXT,
    assignedownergroup TEXT,
    historyflag INTEGER,
    istask INTEGER,
    taskid INTEGER,
    estdur REAL,
    estlabhrs REAL,
    estlabcost REAL,
    estmatcost REAL,
    esttoolcost REAL,
    estservcost REAL,
    esttotalcost REAL,
    actlabhrs REAL,
    actlabcost REAL,
    actmatcost REAL,
    acttoolcost REAL,
    actservcost REAL,
    acttotalcost REAL,
    haschildren INTEGER,
    targstartdate TEXT,
    targcompdate TEXT,
    actstart TEXT,
    actfinish TEXT,
    statusdate TEXT,
    wogroup TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (wonum, workorderid)
);

-- Work order service address table
CREATE TABLE IF NOT EXISTS woserviceaddress (
    woserviceaddressid INTEGER PRIMARY KEY,
    wonum TEXT NOT NULL,
    workorderid INTEGER NOT NULL,
    orgid TEXT,
    addresscode TEXT,
    description TEXT,
    addressline1 TEXT,
    addressline2 TEXT,
    addressline3 TEXT,
    city TEXT,
    country TEXT,
    county TEXT,
    stateprovince TEXT,
    postalcode TEXT,
    langcode TEXT,
    hasld INTEGER,
    addressischanged INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (wonum, workorderid) REFERENCES workorder(wonum, workorderid)
);

-- Work order labor table
CREATE TABLE IF NOT EXISTS wolabor (
    wolaborid INTEGER PRIMARY KEY,
    wonum TEXT NOT NULL,
    workorderid INTEGER NOT NULL,
    laborcode TEXT,
    laborhrs REAL,
    startdate TEXT,
    finishdate TEXT,
    transdate TEXT,
    regularhrs REAL,
    premiumpayhours REAL,
    labtransid INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (wonum, workorderid) REFERENCES workorder(wonum, workorderid)
);

-- Work order material table
CREATE TABLE IF NOT EXISTS womaterial (
    womaterialid INTEGER PRIMARY KEY,
    wonum TEXT NOT NULL,
    workorderid INTEGER NOT NULL,
    itemnum TEXT,
    itemsetid TEXT,
    description TEXT,
    itemqty REAL,
    unitcost REAL,
    linecost REAL,
    storeloc TEXT,
    siteid TEXT,
    orgid TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (wonum, workorderid) REFERENCES workorder(wonum, workorderid)
);

-- Work order tool table
CREATE TABLE IF NOT EXISTS wotool (
    wotoolid INTEGER PRIMARY KEY,
    wonum TEXT NOT NULL,
    workorderid INTEGER NOT NULL,
    toolnum TEXT,
    toolhrs REAL,
    toolrate REAL,
    toolcost REAL,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (wonum, workorderid) REFERENCES workorder(wonum, workorderid)
);
```

### Sync Status Table
```sql
CREATE TABLE IF NOT EXISTS sync_status (
    endpoint TEXT PRIMARY KEY,
    last_sync TIMESTAMP,
    record_count INTEGER,
    status TEXT,
    message TEXT
);
```

## Technical Implementation Approach

### For Each Remaining Endpoint

1. **Analysis Script**
   ```
   analyze_[endpoint].py
   ```
   - Fetch sample data from endpoint
   - Analyze response structure
   - Identify fields and relationships
   - Generate SQL schema

2. **Schema File**
   ```
   [endpoint]_schema.sql
   ```
   - Define tables with proper field types
   - Set up relationships with foreign keys
   - Create indexes for efficient querying

3. **Sync Script**
   ```
   sync_[endpoint].py
   ```
   - Fetch data with appropriate filters
   - Process and transform data
   - Insert/update records in database
   - Update sync_status table

### Implementation Steps for Each Endpoint

1. **MXAPILOCATIONS**
   - Create `analyze_locations.py` to analyze endpoint structure
   - Generate `locations_schema.sql` with tables for locations and related entities
   - Implement `sync_locations.py` to synchronize location data
   - Filter by user's default site

2. **MXAPIASSET**
   - Create `analyze_assets.py` to analyze endpoint structure
   - Generate `assets_schema.sql` with tables for assets and related entities
   - Implement `sync_assets.py` to synchronize asset data
   - Filter by user's default site

3. **MXDOMAIN**
   - Create `analyze_domain.py` to analyze endpoint structure
   - Generate `domain_schema.sql` with tables for domains
   - Implement `sync_domain.py` to synchronize domain data
   - No filtering needed (sync all domains)

4. **MXAPIWODETAIL**
   - Create `analyze_workorders.py` to analyze endpoint structure
   - Generate `workorders_schema.sql` with tables for work orders and related entities
   - Implement `sync_workorders.py` to synchronize work order data
   - Filter by status and user's default site

5. **MXAPIINVENTORY**
   - Create `analyze_inventory.py` to analyze endpoint structure
   - Generate `inventory_schema.sql` with tables for inventory and related entities
   - Implement `sync_inventory.py` to synchronize inventory data
   - Filter by status and user's default site

## Main Synchronization Script

Create a master script `sync_all.py` that:
1. Gets user's default site from local database
2. Calls each endpoint's sync script with appropriate parameters
3. Shows progress and results
4. Updates overall sync status

```python
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
import sync_workorders
import sync_inventory

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Synchronize all Maximo data')
    parser.add_argument('--db-path', type=str, default='~/.maximo_offline/maximo.db',
                        help='Path to the SQLite database file')
    parser.add_argument('--force-full', action='store_true',
                        help='Force a full sync instead of incremental')
    args = parser.parse_args()

    # Get user's default site
    db_path = os.path.expanduser(args.db_path)
    default_site = get_default_site(db_path)

    # Sync each endpoint
    sync_peruser.main(['--db-path', db_path, '--force-full' if args.force_full else ''])
    sync_locations.main(['--db-path', db_path, '--site', default_site, '--force-full' if args.force_full else ''])
    sync_assets.main(['--db-path', db_path, '--site', default_site, '--force-full' if args.force_full else ''])
    sync_domain.main(['--db-path', db_path, '--force-full' if args.force_full else ''])
    sync_workorders.main(['--db-path', db_path, '--site', default_site, '--force-full' if args.force_full else ''])
    sync_inventory.main(['--db-path', db_path, '--site', default_site, '--force-full' if args.force_full else ''])

    # Update overall sync status
    update_sync_status(db_path)

    print("All data synchronized successfully!")

if __name__ == "__main__":
    main()
```

## Final Integration

1. **Database Access Layer**
   - Create a module to provide easy access to offline data
   - Implement methods for common queries
   - Handle data relationships

2. **UI Integration**
   - Add UI elements to initiate sync
   - Show sync progress and status
   - Indicate when app is in offline mode

3. **Change Tracking**
   - Implement tracking of offline changes
   - Queue changes for sync when online
   - Handle conflict resolution

## How to Complete the Implementation

1. **Follow the Pattern**
   - Use the existing `analyze_peruser.py` and `sync_peruser.py` as templates
   - Adapt the code for each endpoint's specific structure
   - Maintain consistent naming and coding style

2. **Incremental Development**
   - Implement one endpoint at a time
   - Test thoroughly after each implementation
   - Refine based on testing results

3. **Performance Optimization**
   - Use chunking for large datasets
   - Implement proper indexing
   - Use incremental sync where possible

4. **Error Handling**
   - Add robust error handling
   - Implement retry logic
   - Provide clear error messages

5. **Documentation**
   - Document each script's purpose and usage
   - Add comments explaining complex logic
   - Create user documentation for the offline feature

## Existing Files

1. **create_maximo_db.py**: Creates the SQLite database with all tables
2. **organization_schema.sql**: Schema for organization-related tables
3. **peruser_schema.sql**: Schema for person-related tables
4. **locations_schema.sql**: Schema for location-related tables
5. **assets_schema.sql**: Schema for asset-related tables
6. **asset_related_tables_schema.sql**: Schema for asset-related tables (meters, specs, etc.)
7. **domain_schema.sql**: Schema for domain-related tables
8. **wodetail_schema.sql**: Schema for work order-related tables
9. **analyze_organization.py**: Analyzes the MXAPIORGANIZATION endpoint
10. **analyze_peruser.py**: Analyzes the MXAPIPERUSER endpoint
11. **analyze_locations.py**: Analyzes the MXAPILOCATIONS endpoint
12. **analyze_assets.py**: Analyzes the MXAPIASSET endpoint
13. **analyze_domain.py**: Analyzes the MXAPIDOMAIN endpoint
14. **analyze_wodetail.py**: Analyzes the MXAPIWODETAIL endpoint
15. **sync_peruser.py**: Synchronizes data from MXAPIPERUSER endpoint
16. **sync_locations.py**: Synchronizes data from MXAPILOCATIONS endpoint
17. **sync_assets.py**: Synchronizes data from MXAPIASSET endpoint
18. **sync_domain.py**: Synchronizes data from MXAPIDOMAIN endpoint
19. **sync_wodetail.py**: Synchronizes data from MXAPIWODETAIL endpoint

## Next Steps

1. ~~Implement `analyze_locations.py` and `sync_locations.py` for the MXAPILOCATIONS endpoint~~ ✅ COMPLETED
2. ~~Implement `analyze_assets.py` and `sync_assets.py` for the MXAPIASSET endpoint~~ ✅ COMPLETED
3. ~~Implement `analyze_domain.py` and `sync_domain.py` for the MXAPIDOMAIN endpoint~~ ✅ COMPLETED
4. ~~Implement `analyze_wodetail.py` and `sync_wodetail.py` for the MXAPIWODETAIL endpoint~~ ✅ COMPLETED
5. Implement `analyze_inventory.py` and `sync_inventory.py` for the MXAPIINVENTORY endpoint
6. Create the master `sync_all.py` script
7. Implement the database access layer and UI integration
8. Test thoroughly with real data and in offline scenarios
