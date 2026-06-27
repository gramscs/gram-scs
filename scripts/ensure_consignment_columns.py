#!/usr/bin/env python3
"""
Ensure the `consignment` table has the columns expected by the current model.

Usage:
  DATABASE_URL="postgresql://user:pass@host:5432/dbname" python scripts/ensure_consignment_columns.py

Use this as the one-time migration step for older Supabase databases before
deploying production traffic. The script is idempotent and safe to run multiple
times.
"""
import os
import sys

from app.db_maintenance import ensure_consignment_columns


def main():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(2)

    try:
        ensure_consignment_columns(dsn)
        print("Schema ensure complete.")
    except Exception as e:
        print(f"ERROR: Failed to apply schema changes: {e}")
        sys.exit(4)


if __name__ == '__main__':
    main()
