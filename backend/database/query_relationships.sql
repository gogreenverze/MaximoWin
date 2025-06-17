-- Set output format
.headers on
.mode column
.width 15 30 15 15

-- Organization details
SELECT orgid, description, organizationid, active, basecurrency1 
FROM organizations 
WHERE orgid = 'USAF';

-- Related sites
SELECT siteid, description, active, systemid
FROM sites 
WHERE orgid = 'USAF';

-- Related addresses
SELECT addresscode, description, address1, address2, address5
FROM addresses 
WHERE orgid = 'USAF';

-- Related billtoshipto records with meaningful joins
SELECT 
    b.siteid, 
    s.description as site_description, 
    b.addresscode, 
    a.description as address_description,
    CASE WHEN b.billtodefault = 1 THEN 'Yes' ELSE 'No' END as default_billto,
    CASE WHEN b.shiptodefault = 1 THEN 'Yes' ELSE 'No' END as default_shipto
FROM billtoshipto b
JOIN sites s ON b.siteid = s.siteid AND b.orgid = s.orgid
JOIN addresses a ON b.addresscode = a.addresscode AND b.orgid = a.orgid
WHERE b.orgid = 'USAF'
ORDER BY b.siteid;
