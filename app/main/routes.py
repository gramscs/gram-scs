from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app.models import Consignment, db
from app import cache, mail
from app.services.logistics import (
    normalize_consignment_number,
    normalize_status,
    normalize_indian_pincode,
    geocode_indian_pincode_with_retry,
    reverse_geocode_pincode_with_retry,
    calculate_eta_breakdown_with_retry,
    get_fallback_eta,
)
from flask_mail import Message
import os
import json
import logging
import re
from datetime import datetime
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates"
)


# ----------------------------
# HOME
# ----------------------------
@main_bp.route("/")
@cache.cached(timeout=300)
def index():
    return render_template("main/index.html")


# ----------------------------
# TRACK
# ----------------------------
@main_bp.route("/track", methods=["GET", "POST"])
def track():
    consignment = None
    eta_debug = None
    error_message = None

    if request.method == "POST":
        try:
            number = request.form.get("consignment_number")
            
            if not number or not number.strip():
                error_message = "Please enter a consignment number."
            else:
                number = number.strip().upper()
                
                # Validate format
                if not re.match(r'^[A-Za-z0-9]{1,16}$', number):
                    error_message = "Invalid consignment number format."
                else:
                    try:
                        consignment = Consignment.query.filter_by(
                            consignment_number=number
                        ).first()

                        if consignment:
                            updated = False

                            # 1) Keep coordinates in sync with pincode when pincode exists.
                            if consignment.pickup_pincode:
                                pickup_geo = geocode_indian_pincode_with_retry(consignment.pickup_pincode)
                                if pickup_geo:
                                    consignment.pickup_lat = pickup_geo["lat"]
                                    consignment.pickup_lng = pickup_geo["lng"]
                                    updated = True
                            elif consignment.pickup_lat is not None and consignment.pickup_lng is not None:
                                # Legacy backfill from coordinates to pincode.
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
                                # Legacy backfill from coordinates to pincode.
                                resolved_drop = reverse_geocode_pincode_with_retry(consignment.drop_lat, consignment.drop_lng)
                                if resolved_drop:
                                    consignment.drop_pincode = resolved_drop
                                    updated = True

                            # 2) Recompute ETA on every Track click when route points exist.
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
                                except Exception as commit_error:
                                    db.session.rollback()
                                    logger.warning("Unable to persist real-time track refresh for %s: %s", consignment.consignment_number, commit_error)
                        
                        if not consignment:
                            error_message = "Consignment not found. Please check the number and try again."
                    except (OperationalError, DatabaseError) as e:
                        logger.error(f"Database error in track: {e}")
                        error_message = "Unable to connect to database. Please try again later."
                    
        except Exception as e:
            logger.error(f"Unexpected error in track: {e}")
            error_message = "An unexpected error occurred. Please try again."

    return render_template(
        "main/track.html",
        consignment=consignment,
        eta_debug=eta_debug,
        error_message=error_message,
    )


# ----------------------------
# ABOUT
# ----------------------------
@main_bp.route("/about")
@cache.cached(timeout=300)
def about():
    return render_template("main/about.html")


# ----------------------------
# CONTACT
# ----------------------------
@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            
            # Validate inputs
            if not name or not email or not message:
                flash("Please fill in all required fields.", "error")
                return render_template("main/contact.html")
            
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash("Please enter a valid email address.", "error")
                return render_template("main/contact.html")
            
            # Send Email
            email_sent = False
            try:
                msg = Message(
                    subject=f"New Contact: {subject or 'No Subject'}",
                    sender=email,
                    recipients=["yourgmail@gmail.com"]
                )

                msg.body = f"""
Name: {name}
Email: {email}

Message:
{message}
"""
                mail.send(msg)
                email_sent = True
                logger.info(f"Contact email sent from {email}")

            except Exception as e:
                logger.error(f"Email sending failed: {e}")
                # Continue to save locally even if email fails

            # Save locally (backup)
            entry = {
                'name': name,
                'email': email,
                'subject': subject,
                'message': message,
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'email_sent': email_sent
            }

            try:
                storage_dir = os.path.join(os.getcwd(), 'storage')
                os.makedirs(storage_dir, exist_ok=True)
                submissions_file = os.path.join(storage_dir, 'contact_submissions.jsonl')
                
                with open(submissions_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + "\n")
                logger.info(f"Contact form saved locally for {email}")
            except IOError as e:
                logger.error(f"Failed to save contact form locally: {e}")
                if not email_sent:
                    flash("There was an issue submitting your message. Please try again.", "error")
                    return render_template("main/contact.html")

            flash("Message sent successfully! We'll get back to you soon.", "success")
            return redirect(url_for("main.contact"))
            
        except Exception as e:
            logger.error(f"Unexpected error in contact form: {e}")
            flash("An unexpected error occurred. Please try again later.", "error")
            return render_template("main/contact.html")

    return render_template("main/contact.html")


# ----------------------------
# NEWSLETTER
# ----------------------------
@main_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    try:
        email = request.form.get('email') or (request.get_json(silent=True) or {}).get('email')

        if not email or not email.strip():
            return jsonify({'success': False, 'message': 'Email address is required'}), 400
        
        email = email.strip().lower()
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'}), 400

        entry = {
            'email': email,
            'subscribed_at': datetime.utcnow().isoformat() + 'Z'
        }

        try:
            storage_dir = os.path.join(os.getcwd(), 'storage')
            os.makedirs(storage_dir, exist_ok=True)
            subs_file = os.path.join(storage_dir, 'newsletter_subscribers.jsonl')
            
            with open(subs_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
            
            logger.info(f"Newsletter subscription: {email}")
            return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter'})
            
        except IOError as e:
            logger.error(f"Failed to save newsletter subscription: {e}")
            return jsonify({'success': False, 'message': 'Unable to process subscription. Please try again later.'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in newsletter subscription: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500


# ----------------------------
# SECRET ADMIN PANEL
# ----------------------------
@main_bp.route("/xk7m2p", methods=["GET"])
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
        logger.error(f"Database error loading admin panel: {e}")
        return render_template("main/xk7m2p.html", consignments=[], error="Unable to load data. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error in admin panel: {e}")
        return render_template("main/xk7m2p.html", consignments=[], error="An unexpected error occurred.")


@main_bp.route("/xk7m2p/save", methods=["POST"])
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
        logger.error(f"Integrity error in admin save: {e}")
        return jsonify({"success": False, "message": "Duplicate consignment number already exists."}), 400
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error(f"Database error in admin save: {e}")
        return jsonify({"success": False, "message": "Database connection error. Please try again."}), 500
    except ValueError as e:
        db.session.rollback()
        logger.error(f"Validation error in admin save: {e}")
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error in admin save: {e}")
        return jsonify({"success": False, "message": "An unexpected error occurred. Please try again."}), 500