"""Example Supabase implementation for ``flask_adapter.py``.

This file is intentionally an example, because table names, bucket names, and
Supabase client setup vary by project. Keep Supabase credentials on the server.
"""

from __future__ import annotations

import io
import os

from flask import Flask, Response, send_file
from supabase import create_client

from flask_adapter import create_track_api_blueprint

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
POD_BUCKET = os.getenv("POD_BUCKET", "pods")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def lookup_consignment(number: str):
    result = (
        supabase.table("consignments")
        .select(
            "consignment_number,status,pickup_pincode,pickup_address,pickup_tag,"
            "pickup_date,drop_pincode,drop_address,drop_tag,drop_date,eta,pod_image"
        )
        .eq("consignment_number", number)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def get_pod_response(number: str):
    consignment = lookup_consignment(number)
    if not consignment or not consignment.get("pod_image"):
        return None

    file_bytes = supabase.storage.from_(POD_BUCKET).download(consignment["pod_image"])
    if not file_bytes:
        return None

    return send_file(
        io.BytesIO(file_bytes),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"{number}_pod",
    )


def create_app():
    app = Flask(__name__, static_folder="../", static_url_path="/track")
    app.register_blueprint(create_track_api_blueprint(lookup_consignment, get_pod_response))

    @app.after_request
    def expose_pod_filename_header(response: Response):
        response.headers.add("Access-Control-Expose-Headers", "Content-Disposition")
        return response

    return app
