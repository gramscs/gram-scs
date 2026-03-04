#!/usr/bin/env python3
"""
Database backup and restore script for Gram SCS.

Features:
- Automated SQLite database backup with timestamp
- Configurable retention policy (keeps last N backups)
- Restore capability from any backup
- Safe backup process (temporary file + atomic rename)
- Logging for audit trail

Usage:
    # Create a backup
    python backup_database.py backup

    # Restore from a specific backup
    python backup_database.py restore backup_2026-03-04_123045.db

    # List available backups
    python backup_database.py list

    # Clean old backups (keeps only last N)
    python backup_database.py clean

Schedule with cron (daily at 2 AM):
    0 2 * * * cd /path/to/gram-scs-it-dept && python backup_database.py backup
"""

import os
import sys
import shutil
import glob
import argparse
from datetime import datetime
from pathlib import Path


# Configuration
DB_PATH = "instance/database.db"
BACKUP_DIR = "backups"
RETENTION_COUNT = 30  # Keep last 30 backups
LOG_FILE = "backups/backup.log"


def ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)


def log_message(message):
    """Log a message to both console and log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    
    ensure_backup_dir()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}")


def create_backup():
    """Create a timestamped backup of the database."""
    if not os.path.exists(DB_PATH):
        log_message(f"ERROR: Database file not found at {DB_PATH}")
        return False
    
    ensure_backup_dir()
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    temp_backup_path = backup_path + ".tmp"
    
    try:
        # Copy to temporary file first (atomic operation)
        log_message(f"Creating backup: {backup_filename}")
        shutil.copy2(DB_PATH, temp_backup_path)
        
        # Rename to final backup name
        os.rename(temp_backup_path, backup_path)
        
        # Get file size
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        log_message(f"SUCCESS: Backup created ({size_mb:.2f} MB)")
        
        # Clean old backups
        clean_old_backups()
        
        return True
    
    except Exception as e:
        log_message(f"ERROR: Backup failed - {str(e)}")
        # Clean up temporary file if it exists
        if os.path.exists(temp_backup_path):
            os.remove(temp_backup_path)
        return False


def list_backups():
    """List all available backups sorted by date."""
    ensure_backup_dir()
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_*.db")), reverse=True)
    
    if not backups:
        log_message("No backups found.")
        return []
    
    log_message(f"Found {len(backups)} backup(s):")
    for backup in backups:
        filename = os.path.basename(backup)
        size_mb = os.path.getsize(backup) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(backup))
        log_message(f"  - {filename} ({size_mb:.2f} MB, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    return backups


def restore_backup(backup_name):
    """Restore database from a backup file."""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    if not os.path.exists(backup_path):
        log_message(f"ERROR: Backup file not found: {backup_name}")
        return False
    
    # Create a safety backup of current database before restoring
    if os.path.exists(DB_PATH):
        safety_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        safety_backup_path = os.path.join(BACKUP_DIR, safety_backup)
        try:
            shutil.copy2(DB_PATH, safety_backup_path)
            log_message(f"Created safety backup: {safety_backup}")
        except Exception as e:
            log_message(f"WARNING: Could not create safety backup: {e}")
    
    try:
        log_message(f"Restoring from: {backup_name}")
        
        # Ensure instance directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Copy backup to database location
        shutil.copy2(backup_path, DB_PATH)
        log_message(f"SUCCESS: Database restored from {backup_name}")
        return True
    
    except Exception as e:
        log_message(f"ERROR: Restore failed - {str(e)}")
        return False


def clean_old_backups():
    """Remove old backups beyond retention policy."""
    ensure_backup_dir()
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_*.db")), reverse=True)
    
    if len(backups) <= RETENTION_COUNT:
        return
    
    # Remove old backups
    backups_to_remove = backups[RETENTION_COUNT:]
    log_message(f"Cleaning {len(backups_to_remove)} old backup(s) (retention: {RETENTION_COUNT})")
    
    for backup in backups_to_remove:
        try:
            os.remove(backup)
            log_message(f"  Removed: {os.path.basename(backup)}")
        except Exception as e:
            log_message(f"  WARNING: Could not remove {os.path.basename(backup)}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Database backup and restore utility for Gram SCS"
    )
    parser.add_argument(
        "action",
        choices=["backup", "restore", "list", "clean"],
        help="Action to perform"
    )
    parser.add_argument(
        "backup_file",
        nargs="?",
        help="Backup filename (required for restore action)"
    )
    
    args = parser.parse_args()
    
    if args.action == "backup":
        success = create_backup()
        sys.exit(0 if success else 1)
    
    elif args.action == "list":
        list_backups()
        sys.exit(0)
    
    elif args.action == "restore":
        if not args.backup_file:
            print("ERROR: Backup filename required for restore action")
            print("Usage: python backup_database.py restore <backup_filename>")
            sys.exit(1)
        success = restore_backup(args.backup_file)
        sys.exit(0 if success else 1)
    
    elif args.action == "clean":
        clean_old_backups()
        sys.exit(0)


if __name__ == "__main__":
    main()
