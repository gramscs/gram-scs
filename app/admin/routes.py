from flask import render_template, request, jsonify
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from datetime import datetime
import json
import logging

from app.admin import admin_bp
from app.models import Consignment, db
from app.services.logistics import (
    normalize_consignment_number,
    normalize_status,
    normalize_indian_pincode,
    geocode_indian_pincode_with_retry,
    calculate_eta_breakdown_with_retry,
    get_fallback_eta,
)

logger = logging.getLogger(__name__)


@admin_bp.route("/xk7m2p", methods=["GET"])
def xk7m2p():
    try:
        consignments = Consignment.query.order_by(Consignment.id.asc()).all()
        rows = [
            {
                "id": c.id,
                "consignment_number": c.consignment_number,
                "status": c.status,
                "pickup_pincode": c.pickup_pincode,
                "drop_pincode": c.drop_pincode,
                "pickup_lat": c.pickup_lat,
                "pickup_lng": c.pickup_lng,
                "drop_lat": c.drop_lat,
                "drop_lng": c.drop_lng,
                "eta": c.eta,
            }
            for c in consignments
        ]
        return render_template("main/xk7m2p.html", consignments=rows)
    except (OperationalError, DatabaseError) as e:
        logger.error("Database error loading admin panel: %s", e)
        return render_template("main/xk7m2p.html", consignments=[], error="Unable to load data. Please try again.")
    except Exception as e:
        logger.error("Unexpected error in admin panel: %s", e)
        return render_template("main/xk7m2p.html", consignments=[], error="An unexpected error occurred.")


@admin_bp.route("/xk7m2p/save", methods=["POST"])
def xk7m2p_save():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", [])

    if not isinstance(rows, list):
        return jsonify({"success": False, "message": "Invalid request payload."}), 400

    try:
        existing = {c.id: c for c in Consignment.query.all()}
        seen_numbers = set()
        incoming_existing_ids = set()
        validated_rows = []

        for row in rows:
            row_id = row.get("id")
            try:
                consignment_number = normalize_consignment_number(row.get("consignment_number"))
                status = normalize_status(row.get("status"))
                pickup_pincode = normalize_indian_pincode(row.get("pickup_pincode"), "pickup_pincode")
                drop_pincode = normalize_indian_pincode(row.get("drop_pincode"), "drop_pincode")
            except ValueError as error:
                return jsonify({"success": False, "message": str(error)}), 400

            if consignment_number in seen_numbers:
                return jsonify({
                    "success": False,
                    "message": f"Duplicate consignment number in sheet: {consignment_number}"
                }), 400
            seen_numbers.add(consignment_number)

            pickup_location = geocode_indian_pincode_with_retry(pickup_pincode)
            if pickup_location is None:
                return jsonify({
                    "success": False,
                    "message": f"Unable to resolve pickup pincode for consignment {consignment_number}."
                }), 400

            drop_location = geocode_indian_pincode_with_retry(drop_pincode)
            if drop_location is None:
                return jsonify({
                    "success": False,
                    "message": f"Unable to resolve drop pincode for consignment {consignment_number}."
                }), 400

            pickup_lat = pickup_location["lat"]
            pickup_lng = pickup_location["lng"]
            drop_lat = drop_location["lat"]
            drop_lng = drop_location["lng"]

            eta_breakdown = calculate_eta_breakdown_with_retry(
                pickup_lat,
                pickup_lng,
                drop_lat,
                drop_lng,
            )
            if eta_breakdown is None:
                eta = get_fallback_eta()
                eta_breakdown = {
                    "eta": eta,
                    "duration_seconds": None,
                    "duration_hours": None,
                    "distance_km": None,
                    "calculated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "route_source": "fallback",
                    "formula": "ETA fallback used because route lookup failed",
                }
            else:
                eta = eta_breakdown["eta"]

            eta_breakdown["pickup_pincode"] = pickup_pincode
            eta_breakdown["drop_pincode"] = drop_pincode
            eta_breakdown["pickup_coords"] = [pickup_lat, pickup_lng]
            eta_breakdown["drop_coords"] = [drop_lat, drop_lng]
            eta_breakdown["pickup_geocode_source"] = pickup_location.get("source")
            eta_breakdown["drop_geocode_source"] = drop_location.get("source")

            if row_id:
                try:
                    row_id = int(row_id)
                except (TypeError, ValueError):
                    return jsonify({"success": False, "message": f"Invalid row id: {row_id}"}), 400

                if row_id not in existing:
                    return jsonify({"success": False, "message": f"Row id {row_id} not found."}), 400
                incoming_existing_ids.add(row_id)
            else:
                row_id = None

            validated_rows.append({
                "id": row_id,
                "consignment_number": consignment_number,
                "status": status,
                "pickup_pincode": pickup_pincode,
                "drop_pincode": drop_pincode,
                "pickup_lat": pickup_lat,
                "pickup_lng": pickup_lng,
                "drop_lat": drop_lat,
                "drop_lng": drop_lng,
                "eta": eta,
                "eta_debug_json": json.dumps(eta_breakdown),
            })

        for existing_id, consignment in existing.items():
            if existing_id not in incoming_existing_ids:
                db.session.delete(consignment)

        db.session.flush()

        for row in validated_rows:
            if row["id"]:
                consignment = existing[row["id"]]
            else:
                consignment = Consignment()
                db.session.add(consignment)

            consignment.consignment_number = row["consignment_number"]
            consignment.status = row["status"]
            consignment.pickup_pincode = row["pickup_pincode"]
            consignment.drop_pincode = row["drop_pincode"]
            consignment.pickup_lat = row["pickup_lat"]
            consignment.pickup_lng = row["pickup_lng"]
            consignment.drop_lat = row["drop_lat"]
            consignment.drop_lng = row["drop_lng"]
            consignment.eta = row["eta"]
            consignment.eta_debug_json = row["eta_debug_json"]

        db.session.commit()
        return jsonify({"success": True, "message": "Sheet saved successfully."})

    except IntegrityError as e:
        db.session.rollback()
        logger.error("Integrity error in admin save: %s", e)
        return jsonify({"success": False, "message": "Duplicate consignment number already exists."}), 400
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error("Database error in admin save: %s", e)
        return jsonify({"success": False, "message": "Database connection error. Please try again."}), 500
    except ValueError as e:
        db.session.rollback()
        logger.error("Validation error in admin save: %s", e)
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error("Unexpected error in admin save: %s", e)
        return jsonify({"success": False, "message": "An unexpected error occurred. Please try again."}), 500
