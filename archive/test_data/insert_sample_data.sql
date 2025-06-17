-- Insert sample organization data
INSERT INTO organizations (
    orgid, description, organizationid, active, basecurrency1, category, 
    clearingacct, companysetid, dfltitemstatus, dfltitemstatus_description, 
    enterby, enterdate, itemsetid, plusgaddassetspec, plusgaddfailcode, _rowstamp
) VALUES (
    'USAF', 'United States Air Force', 8, 1, 'USD', 'STK',
    '0000.0000.00000', 'COMPSET2', 'ACTIVE', 'Active',
    'DATASPLICE', '2021-09-27T02:05:08+00:00', 'ITEMSET2', 1, 1, '115573835'
);

-- Insert sample sites for the organization
INSERT INTO sites (
    siteid, orgid, description, active, systemid, siteuid, vecfreight,
    contact, enterby, enterdate, changeby, changedate, plusgopenomuid, _rowstamp
) VALUES (
    'THULE', 'USAF', 'Thule Air Base', 1, 'THULELOC', 16, '0',
    'WILLIAM.WOMACK', 'DATASPLICE', '2021-09-27T02:12:17+00:00', 'KUBE920000027', '2022-11-07T10:15:45+00:00', 14, '474861215'
);

INSERT INTO sites (
    siteid, orgid, description, active, systemid, siteuid, vecfreight,
    contact, enterby, enterdate, changeby, changedate, plusgopenomuid, _rowstamp
) VALUES (
    'SHEPD', 'USAF', 'Sheppard Air Force Base', 1, 'SHEPDLOC', 24, '0',
    NULL, 'JAIN383011', '2022-01-20T16:48:35+00:00', 'KUBE920000027', '2022-11-07T10:15:49+00:00', 22, '474861216'
);

-- Insert sample addresses for the organization
INSERT INTO addresses (
    addressid, addresscode, orgid, description, address1, address2, address3, address4, address5,
    changeby, changedate, _rowstamp
) VALUES (
    33, '11072', 'USAF', 'Sheppard AFB', '235 9th Avenue Bldg. 1404', 'Wichita Falls', 'TX', '76311', 'US',
    'JAIN383011', '2022-01-20T16:50:34+00:00', '190260224'
);

INSERT INTO addresses (
    addressid, addresscode, orgid, description, address1, address2, address3, address4, address5,
    changeby, changedate, _rowstamp
) VALUES (
    20, '30001', 'USAF', 'Vectrus HQ', '2424 Garden of the Gods Road, Suite 300', 'Colorado Springs', 'CO', '80919', 'US',
    'KRISH113979', '2021-09-27T03:11:36+00:00', '115580885'
);

-- Insert sample billtoshipto records
INSERT INTO billtoshipto (
    billtoshiptoid, siteid, orgid, addresscode, billtodefault, shiptodefault, billto, shipto,
    billtocontact, shiptocontact, _rowstamp
) VALUES (
    31, 'THULE', 'USAF', '30001', 0, 0, NULL, NULL,
    NULL, NULL, '115583526'
);

INSERT INTO billtoshipto (
    billtoshiptoid, siteid, orgid, addresscode, billtodefault, shiptodefault, billto, shipto,
    billtocontact, shiptocontact, _rowstamp
) VALUES (
    37, 'SHEPD', 'USAF', '11072', 1, 1, 1, 1,
    NULL, NULL, '190260395'
);

-- Query to show one organization with its related records
.headers on
.mode column

-- Organization details
SELECT * FROM organizations WHERE orgid = 'USAF';

-- Related sites
SELECT * FROM sites WHERE orgid = 'USAF';

-- Related addresses
SELECT * FROM addresses WHERE orgid = 'USAF';

-- Related billtoshipto records
SELECT b.billtoshiptoid, b.siteid, s.description as site_description, 
       b.addresscode, a.description as address_description,
       b.billtodefault, b.shiptodefault
FROM billtoshipto b
JOIN sites s ON b.siteid = s.siteid AND b.orgid = s.orgid
JOIN addresses a ON b.addresscode = a.addresscode AND b.orgid = a.orgid
WHERE b.orgid = 'USAF';
