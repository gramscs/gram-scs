-- Migration: Create pickup_stations table
-- Created: 2026-04-30
-- Purpose: Add master data table to manage pickup station locations for consignment routing

CREATE TABLE IF NOT EXISTS public.pickup_stations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    pin_code VARCHAR(6) NOT NULL,
    address VARCHAR(1024),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create index on name for frequent lookups during consignment save
CREATE INDEX IF NOT EXISTS idx_pickup_stations_name ON public.pickup_stations(name);

-- Create index on pin_code for internal reference
CREATE INDEX IF NOT EXISTS idx_pickup_stations_pin_code ON public.pickup_stations(pin_code);
