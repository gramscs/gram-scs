-- Idempotent SQL migration to add missing consignment columns.
-- Safe to run multiple times. Adds nullable text/varchar columns only.

-- Try singular table name first (SQLAlchemy default `Consignment` -> `consignment`)
ALTER TABLE IF EXISTS consignment
    ADD COLUMN IF NOT EXISTS pickup_tag VARCHAR(100),
    ADD COLUMN IF NOT EXISTS pickup_date VARCHAR(100),
    ADD COLUMN IF NOT EXISTS drop_tag VARCHAR(100),
    ADD COLUMN IF NOT EXISTS drop_date VARCHAR(100);

-- Also attempt plural table name just in case the DB uses that convention
ALTER TABLE IF EXISTS consignments
    ADD COLUMN IF NOT EXISTS pickup_tag VARCHAR(100),
    ADD COLUMN IF NOT EXISTS pickup_date VARCHAR(100),
    ADD COLUMN IF NOT EXISTS drop_tag VARCHAR(100),
    ADD COLUMN IF NOT EXISTS drop_date VARCHAR(100);

-- End of migration
