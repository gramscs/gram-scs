#!/usr/bin/env python3
"""Re-ingest external POD URLs into permanent storage.

This script migrates `consignments.pod_image` values that currently store
external HTTP(S) URLs. For each row, it downloads the image and re-stores it
using the application's existing `_store_pod_bytes` helper, which writes to
Supabase (when configured) or local instance uploads.
"""

import argparse
import mimetypes
import os
import pathlib
import sys
import uuid
from datetime import datetime, UTC
from urllib.parse import urlparse

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.pod_reingest_reporting import PodReingestReporter


MAX_POD_IMAGE_BYTES = 5 * 1024 * 1024


def _is_external_url(value):
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def _guess_extension(url, content_type):
    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    extension_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/tiff": ".tif",
    }
    if content_type in extension_map:
        return extension_map[content_type]

    guessed = mimetypes.guess_extension(content_type) if content_type else None
    if guessed:
        return ".jpg" if guessed == ".jpe" else guessed

    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    if ext and len(ext) <= 8:
        return ext.lower()

    return ".jpg"


def _download_image(url, timeout):
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_POD_IMAGE_BYTES:
                raise ValueError(
                    f"Image exceeds max allowed size ({MAX_POD_IMAGE_BYTES} bytes)."
                )
        except ValueError:
            # If Content-Length is malformed, ignore and enforce by streamed size.
            pass

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_POD_IMAGE_BYTES:
            raise ValueError(
                f"Image exceeds max allowed size ({MAX_POD_IMAGE_BYTES} bytes)."
            )
        chunks.append(chunk)

    if total == 0:
        raise ValueError("Downloaded image is empty.")

    return b"".join(chunks), response.headers.get("Content-Type")


def _default_report_path():
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return os.path.join("scripts", "reports", f"pod_reingest_{timestamp}.csv")


def _default_failed_report_path():
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return os.path.join("scripts", "reports", f"pod_reingest_failed_{timestamp}.csv")


def run(args):
    from app import create_app
    from app.admin.consignment_controller import _store_pod_bytes
    from app.models import Consignment, db

    def _build_query(only_ids, limit):
        query = Consignment.query.filter(
            db.or_(
                Consignment.pod_image.ilike("http://%"),
                Consignment.pod_image.ilike("https://%"),
            )
        ).order_by(Consignment.id.asc())

        if only_ids:
            query = query.filter(Consignment.id.in_(only_ids))
        if limit and limit > 0:
            query = query.limit(limit)

        return query

    app = create_app()

    with app.app_context():
        rows = _build_query(args.only_id, args.limit).all()
        print(f"Found {len(rows)} candidate rows with external POD URLs.")

        migrated = 0
        failed = 0

        with PodReingestReporter(args.report, args.failed_report) as reporter:
            for row in rows:
                old_value = (row.pod_image or "").strip()
                if not _is_external_url(old_value):
                    continue

                if args.dry_run:
                    reporter.write_full(
                        {
                            "id": row.id,
                            "consignment_number": row.consignment_number,
                            "old_pod_image": old_value,
                            "new_pod_image": "",
                            "status": "dry-run",
                            "error": "",
                        }
                    )
                    continue

                try:
                    image_bytes, content_type = _download_image(old_value, args.timeout)
                    ext = _guess_extension(old_value, content_type)
                    filename = f"reingest_{row.id}_{uuid.uuid4().hex}{ext}"
                    new_value = _store_pod_bytes(filename, image_bytes, content_type=content_type)

                    row.pod_image = new_value
                    db.session.commit()
                    migrated += 1

                    reporter.write_full(
                        {
                            "id": row.id,
                            "consignment_number": row.consignment_number,
                            "old_pod_image": old_value,
                            "new_pod_image": new_value,
                            "status": "migrated",
                            "error": "",
                        }
                    )
                except Exception as error:
                    db.session.rollback()
                    failed += 1
                    reporter.write_full(
                        {
                            "id": row.id,
                            "consignment_number": row.consignment_number,
                            "old_pod_image": old_value,
                            "new_pod_image": "",
                            "status": "failed",
                            "error": str(error),
                        }
                    )
                    reporter.write_failed(
                        row_id=row.id,
                        consignment_number=row.consignment_number,
                        url=old_value,
                        error=error,
                    )

        if args.dry_run:
            print(
                f"Dry run complete. Report: {args.report}. "
                f"Failures report: {args.failed_report}"
            )
            return 0

        print(
            f"Migration complete. Migrated={migrated}, Failed={failed}. "
            f"Report: {args.report}. Failures report: {args.failed_report}"
        )

    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Re-ingest external POD URLs into permanent storage."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidate rows and write a report without modifying DB/storage.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of candidate rows to process.",
    )
    parser.add_argument(
        "--only-id",
        type=int,
        action="append",
        default=[],
        help="Process only specific consignment IDs (repeatable).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds for image downloads (default: 20).",
    )
    parser.add_argument(
        "--report",
        default=_default_report_path(),
        help="CSV report output path.",
    )
    parser.add_argument(
        "--failed-report",
        default=_default_failed_report_path(),
        help="CSV path for failed rows (url + error).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
