-- Main organization table
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

-- Site table (each organization can have multiple sites)
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

-- Address table (each organization can have multiple addresses)
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

-- BillToShipTo table (each site can have multiple bill-to/ship-to relationships)
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

-- Indexes for organization table
CREATE INDEX IF NOT EXISTS idx_organization_active ON organization(active);
CREATE INDEX IF NOT EXISTS idx_organization_organizationid ON organization(organizationid);

-- Indexes for site table
CREATE INDEX IF NOT EXISTS idx_site_orgid ON site(orgid);
CREATE INDEX IF NOT EXISTS idx_site_active ON site(active);

-- Indexes for address table
CREATE INDEX IF NOT EXISTS idx_address_orgid ON address(orgid);

-- Indexes for billtoshipto table
CREATE INDEX IF NOT EXISTS idx_billtoshipto_siteid_orgid ON billtoshipto(siteid, orgid);
CREATE INDEX IF NOT EXISTS idx_billtoshipto_addresscode_orgid ON billtoshipto(addresscode, orgid);
CREATE INDEX IF NOT EXISTS idx_billtoshipto_billtodefault ON billtoshipto(billtodefault);
CREATE INDEX IF NOT EXISTS idx_billtoshipto_shiptodefault ON billtoshipto(shiptodefault);