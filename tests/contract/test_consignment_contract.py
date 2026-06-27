#!/usr/bin/env python3
"""Simple contract test: login and validate `/admin/consignments/list` response shape.

Usage:
  pip install -r requirements-dev.txt
  python tests/contract/test_consignment_contract.py
"""
import os
import sys
import json
from pathlib import Path

import requests
import jsonschema


BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin-pass")


def load_schema(name):
    repo_root = Path(__file__).resolve().parents[2]
    spec_dir = repo_root / "specs"
    with open(spec_dir / name, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    session = requests.Session()

    login_url = BASE + "/admin/login"
    # Submit form credentials
    resp = session.post(login_url, data={"username": ADMIN_USER, "password": ADMIN_PASS}, allow_redirects=False)
    if resp.status_code not in (200, 302):
        print("Login failed: status", resp.status_code)
        sys.exit(2)

    list_url = BASE + "/admin/consignments/list"
    r = session.get(list_url, params={"page": 1, "per_page": 10})
    if r.status_code != 200:
        print("List endpoint returned status", r.status_code)
        print(r.text)
        sys.exit(3)

    data = r.json()

    schema = load_schema("consignment-list-response.schema.json")
    # Prepare resolver base so $ref to consignment.schema.json resolves
    repo_root = Path(__file__).resolve().parents[2]
    spec_dir = repo_root / "specs"
    resolver = jsonschema.RefResolver(base_uri=f"file://{spec_dir}/", referrer=schema)

    try:
        jsonschema.validate(instance=data, schema=schema, resolver=resolver)
        print("Contract validation: OK")
    except Exception as e:
        print("Contract validation: FAILED")
        print(e)
        sys.exit(4)


if __name__ == "__main__":
    main()
