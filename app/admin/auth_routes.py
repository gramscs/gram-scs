"""
Authentication routes for the admin panel.

Routes
------
GET  /admin/login   Render the login form.
POST /admin/login   Validate credentials and set session auth.
GET  /admin/logout  Clear session auth and redirect to login.
"""

import logging

from flask import redirect, render_template, request, url_for

from app.admin import admin_bp
from app.admin.auth import (
    check_admin_credentials,
    is_admin_authenticated,
    login_admin,
    logout_admin,
)

logger = logging.getLogger(__name__)


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    """Render or process the admin login form."""
    if is_admin_authenticated():
        return redirect(url_for("admin.dashboard"))

    error = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if check_admin_credentials(username, password):
            login_admin(username=username)
            logger.info("Admin login successful for user: %s", username)
            return redirect(url_for("admin.dashboard"))

        logger.warning("Failed admin login attempt for username: %s", username)
        error = "Invalid username or password."

    return render_template("admin/login.html", error=error)


@admin_bp.route("/admin/logout", methods=["GET"])
def logout():
    """Clear admin session and redirect to the login page."""
    logout_admin()
    logger.info("Admin logged out.")
    return redirect(url_for("admin.login"))
