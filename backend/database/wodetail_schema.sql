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

-- Indexes for workorder table
CREATE INDEX IF NOT EXISTS idx_workorder_siteid ON workorder(siteid);
CREATE INDEX IF NOT EXISTS idx_workorder_status ON workorder(status);
CREATE INDEX IF NOT EXISTS idx_workorder_location ON workorder(location);
CREATE INDEX IF NOT EXISTS idx_workorder_assetnum ON workorder(assetnum);
CREATE INDEX IF NOT EXISTS idx_workorder_parent ON workorder(parent);
CREATE INDEX IF NOT EXISTS idx_workorder_woclass ON workorder(woclass);
CREATE INDEX IF NOT EXISTS idx_workorder_worktype ON workorder(worktype);
CREATE INDEX IF NOT EXISTS idx_workorder_owner ON workorder(owner);
CREATE INDEX IF NOT EXISTS idx_workorder_assignedownergroup ON workorder(assignedownergroup);
CREATE INDEX IF NOT EXISTS idx_workorder_historyflag ON workorder(historyflag);
CREATE INDEX IF NOT EXISTS idx_workorder_wogroup ON workorder(wogroup);

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

-- Indexes for woserviceaddress table
CREATE INDEX IF NOT EXISTS idx_woserviceaddress_wonum ON woserviceaddress(wonum);
CREATE INDEX IF NOT EXISTS idx_woserviceaddress_workorderid ON woserviceaddress(workorderid);

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

-- Indexes for wolabor table
CREATE INDEX IF NOT EXISTS idx_wolabor_wonum ON wolabor(wonum);
CREATE INDEX IF NOT EXISTS idx_wolabor_workorderid ON wolabor(workorderid);
CREATE INDEX IF NOT EXISTS idx_wolabor_laborcode ON wolabor(laborcode);

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

-- Indexes for womaterial table
CREATE INDEX IF NOT EXISTS idx_womaterial_wonum ON womaterial(wonum);
CREATE INDEX IF NOT EXISTS idx_womaterial_workorderid ON womaterial(workorderid);
CREATE INDEX IF NOT EXISTS idx_womaterial_itemnum ON womaterial(itemnum);
CREATE INDEX IF NOT EXISTS idx_womaterial_siteid ON womaterial(siteid);

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

-- Indexes for wotool table
CREATE INDEX IF NOT EXISTS idx_wotool_wonum ON wotool(wonum);
CREATE INDEX IF NOT EXISTS idx_wotool_workorderid ON wotool(workorderid);
CREATE INDEX IF NOT EXISTS idx_wotool_toolnum ON wotool(toolnum);

