CREATE TABLE IF NOT EXISTS locations (
    location TEXT NOT NULL,
    siteid TEXT NOT NULL,
    description TEXT,
    status TEXT,
    type TEXT,
    type_description TEXT,
    glaccount TEXT,
    orgid TEXT,
    changeby TEXT,
    changedate TEXT,
    disabled INTEGER,
    locationsid INTEGER,
    pluscpmextdate INTEGER,
    useinpopr INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (location, siteid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_locations_status ON locations(status);
CREATE INDEX IF NOT EXISTS idx_locations_siteid ON locations(siteid);
CREATE INDEX IF NOT EXISTS idx_locations_orgid ON locations(orgid);
CREATE INDEX IF NOT EXISTS idx_locations_type ON locations(type);
CREATE INDEX IF NOT EXISTS idx_locations_description ON locations(description);
