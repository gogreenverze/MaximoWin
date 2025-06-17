-- Asset Meters table (ASSETMETER)
CREATE TABLE IF NOT EXISTS assetmeter (
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    metername TEXT NOT NULL,
    active INTEGER,
    lastreading REAL,
    lastreadingdate TEXT,
    lastreadinginspctr TEXT,
    remarks TEXT,
    meter_description TEXT,
    meter_measureunitid TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (assetnum, siteid, metername),
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetmeter
CREATE INDEX IF NOT EXISTS idx_assetmeter_assetnum ON assetmeter(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetmeter_siteid ON assetmeter(siteid);
CREATE INDEX IF NOT EXISTS idx_assetmeter_metername ON assetmeter(metername);
CREATE INDEX IF NOT EXISTS idx_assetmeter_active ON assetmeter(active);

-- Asset Specifications table (ASSETSPEC)
CREATE TABLE IF NOT EXISTS assetspec (
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    assetattrid TEXT NOT NULL,
    alnvalue TEXT,
    numvalue REAL,
    datevalue TEXT,
    changeby TEXT,
    changedate TEXT,
    assetattribute_description TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (assetnum, siteid, assetattrid),
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetspec
CREATE INDEX IF NOT EXISTS idx_assetspec_assetnum ON assetspec(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetspec_siteid ON assetspec(siteid);
CREATE INDEX IF NOT EXISTS idx_assetspec_assetattrid ON assetspec(assetattrid);

-- Asset Documents table (DOCLINKS for assets)
CREATE TABLE IF NOT EXISTS assetdoclinks (
    docinfoid INTEGER PRIMARY KEY,
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    document TEXT,
    description TEXT,
    createdate TEXT,
    changeby TEXT,
    ownertable TEXT,
    ownerid TEXT,
    urltype TEXT,
    urlname TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetdoclinks
CREATE INDEX IF NOT EXISTS idx_assetdoclinks_assetnum ON assetdoclinks(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetdoclinks_siteid ON assetdoclinks(siteid);
CREATE INDEX IF NOT EXISTS idx_assetdoclinks_document ON assetdoclinks(document);

-- Asset Location History table (ASSETLOCATIONS)
CREATE TABLE IF NOT EXISTS assetlocations (
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    location TEXT NOT NULL,
    changedate TEXT NOT NULL,
    changeby TEXT,
    remarks TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (assetnum, siteid, location, changedate),
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetlocations
CREATE INDEX IF NOT EXISTS idx_assetlocations_assetnum ON assetlocations(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetlocations_siteid ON assetlocations(siteid);
CREATE INDEX IF NOT EXISTS idx_assetlocations_location ON assetlocations(location);
CREATE INDEX IF NOT EXISTS idx_assetlocations_changedate ON assetlocations(changedate);

-- Asset Failure Reports table (FAILUREREPORT)
CREATE TABLE IF NOT EXISTS assetfailure (
    failurereportid INTEGER PRIMARY KEY,
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    failurecode TEXT,
    failuredate TEXT,
    problemcode TEXT,
    causecode TEXT,
    remedycode TEXT,
    remarks TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetfailure
CREATE INDEX IF NOT EXISTS idx_assetfailure_assetnum ON assetfailure(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetfailure_siteid ON assetfailure(siteid);
CREATE INDEX IF NOT EXISTS idx_assetfailure_failurecode ON assetfailure(failurecode);
CREATE INDEX IF NOT EXISTS idx_assetfailure_failuredate ON assetfailure(failuredate);

-- Asset Cost History table (ASSETCOSTHISTORY)
CREATE TABLE IF NOT EXISTS assetcosthistory (
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    costdate TEXT NOT NULL,
    totalcost REAL,
    changeby TEXT,
    changedate TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (assetnum, siteid, costdate),
    FOREIGN KEY (assetnum, siteid) REFERENCES assets(assetnum, siteid)
);

-- Create indexes for assetcosthistory
CREATE INDEX IF NOT EXISTS idx_assetcosthistory_assetnum ON assetcosthistory(assetnum);
CREATE INDEX IF NOT EXISTS idx_assetcosthistory_siteid ON assetcosthistory(siteid);
CREATE INDEX IF NOT EXISTS idx_assetcosthistory_costdate ON assetcosthistory(costdate);
