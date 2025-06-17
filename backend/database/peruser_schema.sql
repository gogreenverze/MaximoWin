-- Person table (MXAPIPERUSER)
CREATE TABLE IF NOT EXISTS person (
    -- Primary key and essential identifiers
    personid TEXT PRIMARY KEY,
    personuid INTEGER NOT NULL,

    -- Basic person information
    displayname TEXT,
    firstname TEXT,
    lastname TEXT,
    title TEXT,
    status TEXT NOT NULL,
    status_description TEXT NOT NULL,
    statusdate TEXT NOT NULL,

    -- Contact information
    primaryemail TEXT,
    primaryphone TEXT,

    -- Location information
    locationorg TEXT,
    locationsite TEXT,
    location TEXT,

    -- Address information
    country TEXT,
    city TEXT,
    stateprovince TEXT,
    addressline1 TEXT,
    postalcode TEXT,

    -- Department and organization
    department TEXT,
    supervisor TEXT,
    employeetype TEXT,
    employeetype_description TEXT,

    -- Preferences
    language TEXT,
    timezone TEXT,
    timezone_description TEXT,

    -- Sync metadata
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT
);

-- Maxuser table (nested in MXAPIPERUSER.maxuser)
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

-- Groupuser table (nested in MXAPIPERUSER.maxuser.groupuser)
CREATE TABLE IF NOT EXISTS groupuser (
    groupuserid INTEGER PRIMARY KEY,
    maxuserid INTEGER NOT NULL,
    groupname TEXT NOT NULL,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (maxuserid) REFERENCES maxuser(maxuserid)
);

-- Maxgroup table (nested in MXAPIPERUSER.maxuser.groupuser.maxgroup)
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

-- Groupuser to Maxgroup relationship table
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

-- Person_site table (for tracking which sites a person has access to)
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

-- Indexes for efficient querying
-- Person table indexes
CREATE INDEX IF NOT EXISTS idx_person_status ON person(status);
CREATE INDEX IF NOT EXISTS idx_person_displayname ON person(displayname);
CREATE INDEX IF NOT EXISTS idx_person_personuid ON person(personuid);

-- Maxuser table indexes
CREATE INDEX IF NOT EXISTS idx_maxuser_personid ON maxuser(personid);
CREATE INDEX IF NOT EXISTS idx_maxuser_userid ON maxuser(userid);
CREATE INDEX IF NOT EXISTS idx_maxuser_status ON maxuser(status);
CREATE INDEX IF NOT EXISTS idx_maxuser_defsite ON maxuser(defsite);
CREATE INDEX IF NOT EXISTS idx_maxuser_insertsite ON maxuser(insertsite);

-- Groupuser table indexes
CREATE INDEX IF NOT EXISTS idx_groupuser_maxuserid ON groupuser(maxuserid);
CREATE INDEX IF NOT EXISTS idx_groupuser_groupname ON groupuser(groupname);

-- Maxgroup table indexes
CREATE INDEX IF NOT EXISTS idx_maxgroup_groupname ON maxgroup(groupname);

-- Groupuser_maxgroup table indexes
CREATE INDEX IF NOT EXISTS idx_groupuser_maxgroup_groupuserid ON groupuser_maxgroup(groupuserid);
CREATE INDEX IF NOT EXISTS idx_groupuser_maxgroup_maxgroupid ON groupuser_maxgroup(maxgroupid);

-- Person_site indexes
CREATE INDEX IF NOT EXISTS idx_person_site_personid ON person_site(personid);
CREATE INDEX IF NOT EXISTS idx_person_site_siteid ON person_site(siteid);
CREATE INDEX IF NOT EXISTS idx_person_site_isdefault ON person_site(isdefault);
CREATE INDEX IF NOT EXISTS idx_person_site_isinsert ON person_site(isinsert);