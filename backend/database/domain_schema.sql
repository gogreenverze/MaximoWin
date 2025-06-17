-- Main domains table
CREATE TABLE IF NOT EXISTS domains (
    domainid TEXT NOT NULL,
    domaintype TEXT NOT NULL,
    maxtype TEXT,
    maxtype_description TEXT,
    description TEXT,
    internal INTEGER NOT NULL,
    internal_description TEXT NOT NULL,
    domaintype_description TEXT NOT NULL,
    length INTEGER,
    maxdomainid INTEGER NOT NULL,
    scale INTEGER,
    nevercache INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (domainid)
);

-- Create indexes for domains
CREATE INDEX IF NOT EXISTS idx_domains_domaintype ON domains(domaintype);

-- Synonym domain values table (for SYNONYM type domains)
CREATE TABLE IF NOT EXISTS domain_values (
    domainid TEXT NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    maxvalue TEXT,
    defaults INTEGER,
    internal INTEGER,
    _rowstamp TEXT,
    _last_sync TIMESTAMP,
    _sync_status TEXT,
    PRIMARY KEY (domainid, value),
    FOREIGN KEY (domainid) REFERENCES domains(domainid)
);

-- Create indexes for domain_values
CREATE INDEX IF NOT EXISTS idx_domain_values_domainid ON domain_values(domainid);
CREATE INDEX IF NOT EXISTS idx_domain_values_value ON domain_values(value);
CREATE INDEX IF NOT EXISTS idx_domain_values_description ON domain_values(description);