-- Migration: Create eta_master_records table
-- Created: 2026-04-30
-- Purpose: Store ETA (Estimated Time of Arrival) master data for logistics routing

CREATE TABLE IF NOT EXISTS public.eta_master_records (
    id SERIAL PRIMARY KEY,
    record_key VARCHAR(128) UNIQUE NOT NULL,
    sno INTEGER,
    pin_code VARCHAR(10) NOT NULL,
    pickup_station VARCHAR(255) NOT NULL,
    state_ut VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    pickup_location VARCHAR(255) NOT NULL,
    delivery_location VARCHAR(255) NOT NULL,
    tat_in_days FLOAT NOT NULL,
    zone VARCHAR(50) NOT NULL,
    source_filename VARCHAR(255),
    source_row_number INTEGER,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create index on record_key for fast lookups
CREATE INDEX IF NOT EXISTS idx_eta_master_records_key ON public.eta_master_records(record_key);

-- Create index on pin_code for search queries
CREATE INDEX IF NOT EXISTS idx_eta_master_records_pin_code ON public.eta_master_records(pin_code);

-- Create index on pickup_station for filtering
CREATE INDEX IF NOT EXISTS idx_eta_master_records_pickup_station ON public.eta_master_records(pickup_station);
