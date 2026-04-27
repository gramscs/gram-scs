from flask import render_template, jsonify, send_file, session
from sqlalchemy.exc import OperationalError, DatabaseError
from datetime import datetime, UTC
import json
import logging
import io

from app import limiter
from app.admin import admin_bp
from app.admin.auth import require_admin
from app.eta_master.models import EtaMasterRecord
from app.models import Consignment, Lead, NewsletterSubscriber

logger = logging.getLogger(__name__)

LARGE_BACKUP_ROW_THRESHOLD = 10000


@admin_bp.route("/admin/dashboard", methods=["GET"])
@require_admin
def dashboard():
    """Admin dashboard – protected landing page after login."""
    return render_template("admin/dashboard.html")


def _to_json_safe(value):
    """Convert model values into JSON-serializable primitives."""
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()

    return str(value)


def _serialize_model_row(model_row, excluded_fields=None):
    """Serialize a SQLAlchemy model instance using mapped table columns only."""
    excluded_fields = set(excluded_fields or [])
    serialized = {}

    for column in model_row.__table__.columns:
        if column.name in excluded_fields:
            continue
        serialized[column.name] = _to_json_safe(getattr(model_row, column.name))

    return serialized


@admin_bp.route("/admin/generate-backup", methods=["GET"])
@limiter.limit("3 per minute")
@require_admin
def generate_backup():
    """Generate a one-shot JSON backup of all admin-relevant tables."""
    admin_user = session.get("admin_username") or "unknown"
    started_at = datetime.now(UTC).isoformat()

    try:
        table_specs = [
            ("consignments", Consignment, {"eta_debug_json"}),
            ("leads", Lead, set()),
            ("newsletter_subscribers", NewsletterSubscriber, set()),
            ("eta_master_records", EtaMasterRecord, set()),
        ]

        backup_payload = {}
        table_counts = {}

        for table_name, model_class, excluded_fields in table_specs:
            rows = model_class.query.order_by(model_class.id.asc()).all()
            backup_payload[table_name] = [
                _serialize_model_row(row, excluded_fields=excluded_fields)
                for row in rows
            ]
            table_counts[table_name] = len(rows)

        total_rows = sum(table_counts.values())
        if total_rows > LARGE_BACKUP_ROW_THRESHOLD:
            logger.warning(
                "Large admin backup requested by %s: total_rows=%s threshold=%s",
                admin_user,
                total_rows,
                LARGE_BACKUP_ROW_THRESHOLD,
            )

        backup_payload["metadata"] = {
            "generated_at": started_at,
            "generated_by": admin_user,
            "total_rows": total_rows,
            "table_counts": table_counts,
        }

        backup_json = json.dumps(backup_payload, ensure_ascii=True, indent=2)
        buffer = io.BytesIO()
        buffer.write(backup_json.encode("utf-8"))
        buffer.seek(0)

        filename = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"

        logger.info(
            "Admin backup generated successfully by %s at %s (total_rows=%s)",
            admin_user,
            started_at,
            total_rows,
        )

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/json",
        )
    except Exception as e:
        logger.error("Admin backup generation failed for %s: %s", admin_user, e, exc_info=True)
        return jsonify({"success": False, "message": "Failed to generate backup."}), 500


@admin_bp.route("/admin/leads", methods=["GET"], endpoint="leads_panel")
@require_admin
def leads_panel():
    try:
        leads = Lead.query.order_by(Lead.created_at.desc(), Lead.id.desc()).all()
        rows = [
            {
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "phone": lead.phone,
                "subject": lead.subject,
                "message": lead.message,
                "created_at": lead.created_at.strftime("%Y-%m-%d %H:%M:%S") if lead.created_at else "",
            }
            for lead in leads
        ]
        return render_template("admin/leads.html", leads=rows)
    except (OperationalError, DatabaseError) as e:
        logger.error("Database error loading leads panel: %s", e)
        return render_template("admin/leads.html", leads=[], error="Unable to load leads right now.")
    except Exception as e:
        logger.error("Unexpected error loading leads panel: %s", e)
        return render_template("admin/leads.html", leads=[], error="An unexpected error occurred.")
