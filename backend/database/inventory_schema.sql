CREATE TABLE IF NOT EXISTS inventory (
    about TEXT,
    asl INTEGER,
    autocalcrop INTEGER,
    avblbalance REAL,
    benchstock INTEGER,
    bincnt TEXT,
    binnum TEXT,
    ccf INTEGER,
    conditioncode TEXT,
    consignment INTEGER,
    costtype TEXT,
    costtype_description TEXT,
    curbal REAL,
    curbaltotal REAL,
    deliverytime INTEGER,
    expiredqty REAL,
    hardresissue INTEGER,
    haschildinvbalance INTEGER,
    internal INTEGER,
    inventoryid INTEGER NOT NULL,
    invreserveqty REAL,
    issue1yrago REAL,
    issue2yrago REAL,
    issue3yrago REAL,
    issueunit TEXT,
    issueytd REAL,
    itemnum TEXT,
    itemsetid TEXT,
    itemtype TEXT,
    lastissuedate TEXT,
    location TEXT,
    maxlevel REAL,
    minlevel REAL,
    orderqty REAL,
    orderunit TEXT,
    orgid TEXT,
    reorder INTEGER,
    reservedqty REAL,
    shippedqty REAL,
    siteid TEXT,
    stagedqty REAL,
    status TEXT,
    status_description TEXT,
    statusdate TEXT,
    statusiface INTEGER,
    vecatc INTEGER,
    veccritical INTEGER,
    vendor TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (inventoryid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(status);
CREATE INDEX IF NOT EXISTS idx_inventory_siteid ON inventory(siteid);
CREATE INDEX IF NOT EXISTS idx_inventory_location ON inventory(location);
CREATE INDEX IF NOT EXISTS idx_inventory_itemnum ON inventory(itemnum);

-- Related table for matrectrans
CREATE TABLE IF NOT EXISTS inventory_matrectrans (
    inventory_matrectransid INTEGER PRIMARY KEY AUTOINCREMENT,
    inventoryid INTEGER NOT NULL,
    tax2 REAL,
    tax1 REAL,
    tax4 REAL,
    matrectransid INTEGER,
    tax3 REAL,
    localref TEXT,
    itemsetid TEXT,
    receivedunit TEXT,
    tax6 REAL,
    tax5 REAL,
    tax8 REAL,
    tax7 REAL,
    currencycode TEXT,
    linecost REAL,
    receiptquantity REAL,
    linetype_description TEXT,
    financialperiod TEXT,
    commoditygroup TEXT,
    fromsiteid TEXT,
    actualdate TEXT,
    siteid TEXT,
    tostoreloc TEXT,
    enterbyemail TEXT,
    issue INTEGER,
    commodity TEXT,
    about TEXT,
    consignment INTEGER,
    remark TEXT,
    currencylinecost REAL,
    costinfo INTEGER,
    actualcost REAL,
    ifscnf INTEGER,
    rejectqty REAL,
    frombin TEXT,
    transdate TEXT,
    orgid TEXT,
    unitcost REAL,
    conversion REAL,
    outside INTEGER,
    curbal REAL,
    issuetype TEXT,
    itemnum TEXT,
    fromstoreloc TEXT,
    linetype TEXT,
    totalcurbal REAL,
    issuetype_description TEXT,
    exchangerate REAL,
    prorated INTEGER,
    tobin TEXT,
    newsite TEXT,
    description TEXT,
    linecost2 REAL,
    vecstage INTEGER,
    enteredastask INTEGER,
    enterby TEXT,
    loadedcost REAL,
    exchangerate2 REAL,
    currencyunitcost REAL,
    inspectedqty REAL,
    quantity REAL,
    conditioncode TEXT,
    fromconditioncode TEXT,
    condrate INTEGER,
    oldavgcost REAL,
    receiptref INTEGER,
    polinenum INTEGER,
    porevisionnum INTEGER,
    status TEXT,
    status_description TEXT,
    ponum TEXT,
    positeid TEXT,
    glcreditacct TEXT,
    gldebitacct TEXT,
    ifsresponse TEXT,
    sendersysid TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (inventoryid) REFERENCES inventory(inventoryid)
);

-- Indexes for related table
CREATE INDEX IF NOT EXISTS idx_inventory_matrectrans_inventoryid ON inventory_matrectrans(inventoryid);

-- Related table for transfercuritem
CREATE TABLE IF NOT EXISTS inventory_transfercuritem (
    inventory_transfercuritemid INTEGER PRIMARY KEY AUTOINCREMENT,
    inventoryid INTEGER NOT NULL,
    fromavblbalance REAL,
    linecost REAL,
    localref TEXT,
    fromstoreloc TEXT,
    tositeid TEXT,
    orgid TEXT,
    quantity REAL,
    unitcost REAL,
    about TEXT,
    islot INTEGER,
    frombin TEXT,
    conditioncode TEXT,
    fromconditioncode TEXT,
    fromcurbal REAL,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (inventoryid) REFERENCES inventory(inventoryid)
);

-- Indexes for related table
CREATE INDEX IF NOT EXISTS idx_inventory_transfercuritem_inventoryid ON inventory_transfercuritem(inventoryid);

-- Related table for invcost
CREATE TABLE IF NOT EXISTS inventory_invcost (
    inventory_invcostid INTEGER PRIMARY KEY AUTOINCREMENT,
    inventoryid INTEGER NOT NULL,
    stdcost REAL,
    invcostid INTEGER,
    localref TEXT,
    avgcost REAL,
    lastcost REAL,
    orgid TEXT,
    about TEXT,
    condrate INTEGER,
    conditioncode TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (inventoryid) REFERENCES inventory(inventoryid)
);

-- Indexes for related table
CREATE INDEX IF NOT EXISTS idx_inventory_invcost_inventoryid ON inventory_invcost(inventoryid);

-- Related table for itemcondition
CREATE TABLE IF NOT EXISTS inventory_itemcondition (
    inventory_itemconditionid INTEGER PRIMARY KEY AUTOINCREMENT,
    inventoryid INTEGER NOT NULL,
    localref TEXT,
    hasld INTEGER,
    description TEXT,
    conditioncode TEXT,
    about TEXT,
    condrate REAL,
    itemconditionid INTEGER,
    langcode TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (inventoryid) REFERENCES inventory(inventoryid)
);

-- Indexes for related table
CREATE INDEX IF NOT EXISTS idx_inventory_itemcondition_inventoryid ON inventory_itemcondition(inventoryid);

-- Related table for invbalances
CREATE TABLE IF NOT EXISTS inventory_invbalances (
    inventory_invbalancesid INTEGER PRIMARY KEY AUTOINCREMENT,
    inventoryid INTEGER NOT NULL,
    nextphycntdate TEXT,
    localref TEXT,
    binnum TEXT,
    orgid TEXT,
    invbalancesid INTEGER,
    physcnt REAL,
    conditioncode TEXT,
    about TEXT,
    curbal REAL,
    reconciled INTEGER,
    stagedcurbal REAL,
    expiredqty REAL,
    stagingbin INTEGER,
    physcntdate TEXT,
    sendersysid TEXT,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    FOREIGN KEY (inventoryid) REFERENCES inventory(inventoryid)
);

-- Indexes for related table
CREATE INDEX IF NOT EXISTS idx_inventory_invbalances_inventoryid ON inventory_invbalances(inventoryid);