#!/usr/bin/env python3
"""Application-level PostgreSQL backup/restore utility for consignments."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from app import create_app
from app.models import Consignment, db

BACKUP_DIR = "backups"
RETENTION_COUNT = 30
LOG_FILE = "backups/backup.log"


def ensure_backup_dir():
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)


def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    ensure_backup_dir()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")


def list_backup_files():
    ensure_backup_dir()
    return sorted(Path(BACKUP_DIR).glob("backup_*.json"), reverse=True)


def clean_old_backups():
    backups = list_backup_files()
    if len(backups) <= RETENTION_COUNT:
        return
    for path in backups[RETENTION_COUNT:]:
        path.unlink(missing_ok=True)
        log_message(f"Removed old backup: {path.name}")


def create_backup():
    app = create_app()
    with app.app_context():
        rows = Consignment.query.order_by(Consignment.id.asc()).all()
        payload = [
            {
                "consignment_number": row.consignment_number,
                "status": row.status,
                "pickup_pincode": row.pickup_pincode,
                "drop_pincode": row.drop_pincode,
                "pickup_lat": row.pickup_lat,
                "pickup_lng": row.pickup_lng,
                "drop_lat": row.drop_lat,
                "drop_lng": row.drop_lng,
                "eta": row.eta,
                "eta_debug_json": row.eta_debug_json,
            }
            for row in rows
        ]

    ensure_backup_dir()
    backup_name = f"backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
    backup_path = Path(BACKUP_DIR) / backup_name
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)

    log_message(f"Backup created: {backup_name} (rows={len(payload)})")
    clean_old_backups()


def list_backups():
    backups = list_backup_files()
    if not backups:
        log_message("No backups found.")
        return
    log_message(f"Found {len(backups)} backup(s):")
    for path in backups:
        size_mb = path.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        log_message(f"  - {path.name} ({size_mb:.2f} MB, {mtime})")


def restore_backup(backup_file):
    backup_path = Path(BACKUP_DIR) / backup_file
    if not backup_path.exists():
        log_message(f"ERROR: Backup file not found: {backup_file}")
        return 1

    with open(backup_path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    app = create_app()
    with app.app_context():
        existing_map = {
            row.consignment_number: row
            for row in Consignment.query.all()
        }

        for item in rows:
            number = item.get("consignment_number")
            if not number:
                continue

            entity = existing_map.get(number)
            if not entity:
                entity = Consignment(consignment_number=number)
                db.session.add(entity)

            entity.status = item.get("status")
            entity.pickup_pincode = item.get("pickup_pincode")
            entity.drop_pincode = item.get("drop_pincode")
            entity.pickup_lat = item.get("pickup_lat")
            entity.pickup_lng = item.get("pickup_lng")
            entity.drop_lat = item.get("drop_lat")
            entity.drop_lng = item.get("drop_lng")
            entity.eta = item.get("eta")
            entity.eta_debug_json = item.get("eta_debug_json")

        db.session.commit()

    log_message(f"Restore complete from: {backup_file} (rows={len(rows)})")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Backup and restore consignments (PostgreSQL)")
    parser.add_argument("action", choices=["backup", "list", "restore", "clean"])
    parser.add_argument("backup_file", nargs="?")
    args = parser.parse_args()

    if args.action == "backup":
        create_backup()
        return 0
    if args.action == "list":
        list_backups()
        return 0
    if args.action == "clean":
        clean_old_backups()
        return 0
    if args.action == "restore":
        if not args.backup_file:
            print("ERROR: backup filename is required for restore")
            return 1
        return restore_backup(args.backup_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
