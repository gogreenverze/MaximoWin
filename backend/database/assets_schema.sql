CREATE TABLE IF NOT EXISTS assets (
    assetnum TEXT NOT NULL,
    siteid TEXT NOT NULL,
    description TEXT,
    status TEXT,
    location TEXT,
    parent TEXT,
    serialnum TEXT,
    orgid TEXT,
    changeby TEXT,
    changedate TEXT,
    disabled INTEGER,
    assetid INTEGER,
    assettag TEXT,
    isrunning INTEGER,
    moved INTEGER,
    priority INTEGER,
    purchaseprice REAL,
    replacecost REAL,
    totalcost REAL,
    vendor TEXT,
    manufacturer TEXT,
    installdate TEXT,
    status_description TEXT,
    type_description TEXT,
    type TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (assetnum, siteid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_siteid ON assets(siteid);
CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location);
CREATE INDEX IF NOT EXISTS idx_assets_parent ON assets(parent);
CREATE INDEX IF NOT EXISTS idx_assets_orgid ON assets(orgid);
