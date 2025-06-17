CREATE TABLE IF NOT EXISTS locations (
    location TEXT NOT NULL,
    siteid TEXT NOT NULL,
    _rowstamp TEXT,
    autowogen INTEGER NOT NULL,
    status TEXT NOT NULL,
    changeby TEXT NOT NULL,
    orgid TEXT NOT NULL,
    plusgleaking INTEGER NOT NULL,
    expectedlife INTEGER NOT NULL,
    pluscloop INTEGER NOT NULL,
    pluscpmextdate INTEGER NOT NULL,
    plusgcomcrit INTEGER NOT NULL,
    plusgenvcrit INTEGER NOT NULL,
    isdefault INTEGER NOT NULL,
    islocked INTEGER NOT NULL,
    plusgistemp INTEGER NOT NULL,
    plusgispassvalve INTEGER NOT NULL,
    siteid TEXT NOT NULL,
    statusdate TEXT NOT NULL,
    plusgriskassessed INTEGER NOT NULL,
    description TEXT NOT NULL,
    plusgqualitycritical INTEGER NOT NULL,
    useinpopr INTEGER NOT NULL,
    disabled INTEGER NOT NULL,
    isrepairfacility INTEGER NOT NULL,
    locationsid INTEGER NOT NULL,
    plusgexregistered INTEGER NOT NULL,
    plusgsafetycrit INTEGER NOT NULL,
    replacecost REAL NOT NULL,
    changedate TEXT NOT NULL,
    status_description TEXT NOT NULL,
    plusgopenomuid INTEGER NOT NULL,
    plusgpermitreq INTEGER NOT NULL,
    type_description TEXT NOT NULL,
    type TEXT NOT NULL,
    billtoaddresscode TEXT ,
    autolocate TEXT ,
    shiptoaddresscode TEXT ,
    glaccount TEXT ,
    sendersysid TEXT
    ,_last_sync TIMESTAMP
    ,_sync_status TEXT
    ,PRIMARY KEY (location, siteid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_locations_status ON locations(status);
CREATE INDEX IF NOT EXISTS idx_locations_siteid ON locations(siteid);
CREATE INDEX IF NOT EXISTS idx_locations_orgid ON locations(orgid);
CREATE INDEX IF NOT EXISTS idx_locations_type ON locations(type);
CREATE INDEX IF NOT EXISTS idx_locations_description ON locations(description);