"""Flask backend adapter for the portable tracking widget.

Mount this blueprint in the host Flask app when you want the static files in
``track/`` to call a same-origin API instead of querying Supabase directly from
the browser.

The host app owns the real data lookup. Pass two callables to
``create_track_api_blueprint``:

- ``lookup_consignment(number)`` -> dict | None
- ``get_pod_response(number)`` -> Flask Response | None

Both callables run server-side, so they can safely use private Supabase service
keys, database credentials, or internal APIs.
"""

from __future__ import annotations

import re
from typing import Callable, Mapping, Optional

from flask import Blueprint, Response, jsonify

CONSIGNMENT_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")

ConsignmentLookup = Callable[[str], Optional[Mapping[str, object]]]
PodResponseLookup = Callable[[str], Optional[Response]]


def create_track_api_blueprint(
    lookup_consignment: ConsignmentLookup,
    get_pod_response: PodResponseLookup,
    *,
    url_prefix: str = "/api/track",
) -> Blueprint:
    """Create API routes expected by ``track/track.js``.

    The returned blueprint exposes:

    - ``GET /api/track/<number>`` for JSON shipment details.
    - ``GET /api/track/<number>/pod`` for POD file download/streaming.
    """

    track_api = Blueprint("portable_track_api", __name__, url_prefix=url_prefix)

    @track_api.get("/<number>")
    def shipment(number: str):
        normalized = _normalize_number(number)
        if not normalized:
            return _error("Invalid consignment number format.", 400)

        data = lookup_consignment(normalized)
        if not data:
            return _error("Consignment not found. Please check the number and try again.", 404)

        return jsonify({"success": True, "data": dict(data)})

    @track_api.get("/<number>/pod")
    def pod(number: str):
        normalized = _normalize_number(number)
        if not normalized:
            return _error("Invalid consignment number format.", 400)

        response = get_pod_response(normalized)
        if not response:
            return _error("No POD found.", 404)

        return response

    return track_api


def _normalize_number(number: str) -> Optional[str]:
    value = (number or "").strip().upper()
    if not CONSIGNMENT_NUMBER_PATTERN.fullmatch(value):
        return None
    return value


def _error(message: str, status_code: int):
    return jsonify({"success": False, "message": message}), status_code
