import json
import logging
import re

from flask import Blueprint, render_template, request
from sqlalchemy.exc import DatabaseError, OperationalError

from app.models import db
from app.track.models import TrackConsignment
from app.services.logistics import (
    calculate_eta_breakdown_with_retry,
    geocode_indian_pincode_with_retry,
    reverse_geocode_pincode_with_retry,
)

logger = logging.getLogger(__name__)

track_bp = Blueprint("track", __name__, template_folder="templates")

CONSIGNMENT_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]{1,16}$")


@track_bp.route("/track", methods=["GET", "POST"])
def track_page():
    consignment = None
    eta_debug = None
    error_message = None

    if request.method == "POST":
        number = (request.form.get("consignment_number") or "").strip().upper()

        if not number:
            error_message = "Please enter a consignment number."
            logger.warning("Rejected empty consignment lookup request")
        elif not CONSIGNMENT_NUMBER_PATTERN.fullmatch(number):
            error_message = "Invalid consignment number format."
            logger.warning("Rejected invalid consignment number: %s", number)
        else:
            logger.info("Track lookup received for consignment %s", number)
            try:
                consignment = TrackConsignment.query.filter_by(consignment_number=number).first()

                if consignment:
                    logger.info("Shipment found for consignment %s", number)
                    updated = False

                    if consignment.pickup_pincode:
                        pickup_geo = geocode_indian_pincode_with_retry(consignment.pickup_pincode)
                        if pickup_geo:
                            consignment.pickup_lat = pickup_geo["lat"]
                            consignment.pickup_lng = pickup_geo["lng"]
                            updated = True
                    elif consignment.pickup_lat is not None and consignment.pickup_lng is not None:
                        resolved_pickup = reverse_geocode_pincode_with_retry(consignment.pickup_lat, consignment.pickup_lng)
                        if resolved_pickup:
                            consignment.pickup_pincode = resolved_pickup
                            updated = True

                    if consignment.drop_pincode:
                        drop_geo = geocode_indian_pincode_with_retry(consignment.drop_pincode)
                        if drop_geo:
                            consignment.drop_lat = drop_geo["lat"]
                            consignment.drop_lng = drop_geo["lng"]
                            updated = True
                    elif consignment.drop_lat is not None and consignment.drop_lng is not None:
                        resolved_drop = reverse_geocode_pincode_with_retry(consignment.drop_lat, consignment.drop_lng)
                        if resolved_drop:
                            consignment.drop_pincode = resolved_drop
                            updated = True

                    if (
                        consignment.pickup_lat is not None
                        and consignment.pickup_lng is not None
                        and consignment.drop_lat is not None
                        and consignment.drop_lng is not None
                    ):
                        breakdown = calculate_eta_breakdown_with_retry(
                            consignment.pickup_lat,
                            consignment.pickup_lng,
                            consignment.drop_lat,
                            consignment.drop_lng,
                        )
                        if breakdown is not None:
                            breakdown["pickup_pincode"] = consignment.pickup_pincode
                            breakdown["drop_pincode"] = consignment.drop_pincode
                            breakdown["pickup_coords"] = [consignment.pickup_lat, consignment.pickup_lng]
                            breakdown["drop_coords"] = [consignment.drop_lat, consignment.drop_lng]
                            consignment.eta = breakdown["eta"]
                            consignment.eta_debug_json = json.dumps(breakdown)
                            eta_debug = breakdown
                            updated = True

                    if eta_debug is None and consignment.eta_debug_json:
                        try:
                            eta_debug = json.loads(consignment.eta_debug_json)
                        except (TypeError, ValueError):
                            eta_debug = None

                    if updated:
                        try:
                            db.session.commit()
                            logger.info("Shipment tracking data refreshed for %s", number)
                        except Exception as commit_error:
                            db.session.rollback()
                            logger.warning(
                                "Unable to persist real-time track refresh for %s: %s",
                                consignment.consignment_number,
                                commit_error,
                            )
                else:
                    logger.info("Shipment not found for consignment %s", number)
                    error_message = "Consignment not found. Please check the number and try again."
            except (OperationalError, DatabaseError) as error:
                logger.error("Database error while tracking %s: %s", number, error)
                error_message = "Unable to connect to database. Please try again later."
            except Exception:
                logger.exception("Unexpected error while tracking %s", number)
                error_message = "An unexpected error occurred. Please try again."

    return render_template(
        "track/track.html",
        consignment=consignment,
        eta_debug=eta_debug,
        error_message=error_message,
    )
