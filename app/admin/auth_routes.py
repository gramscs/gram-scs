"""
Authentication routes for the admin panel.

Routes
------
GET  /admin/login   Render the login form.
POST /admin/login   Validate credentials and issue JWT cookies.
GET  /admin/logout  Clear JWT cookies and redirect to login.
POST /admin/refresh Exchange a valid refresh token for a new access token.
"""

import logging

from flask import render_template, request, redirect, url_for, jsonify, make_response

from app.admin import admin_bp
from app.admin.auth import (
    check_admin_credentials,
    generate_access_token,
    generate_refresh_token,
    verify_token,
    set_auth_cookies,
    clear_auth_cookies,
    ACCESS_COOKIE,
    REFRESH_COOKIE,
)

logger = logging.getLogger(__name__)


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    """Render or process the admin login form.

    GET  – Return the login page (redirect to dashboard if already logged in).
    POST – Validate credentials; on success set auth cookies and redirect to
           ``/admin/dashboard``.
    """
    # Already authenticated → skip login form.
    existing_token = request.cookies.get(ACCESS_COOKIE)
    if existing_token and verify_token(existing_token, "access"):
        return redirect(url_for("admin.dashboard"))

    error = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if check_admin_credentials(username, password):
            access_token = generate_access_token()
            refresh_token = generate_refresh_token()

            logger.info("Admin login successful for user: %s", username)
            response = make_response(redirect(url_for("admin.dashboard")))
            set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
            return response

        logger.warning("Failed admin login attempt for username: %s", username)
        error = "Invalid username or password."

    return render_template("admin/login.html", error=error)


@admin_bp.route("/admin/logout", methods=["GET"])
def logout():
    """Clear admin JWT cookies and redirect to the login page."""
    response = make_response(redirect(url_for("admin.login")))
    clear_auth_cookies(response)
    logger.info("Admin logged out.")
    return response


@admin_bp.route("/admin/refresh", methods=["POST"])
def refresh():
    """Issue a new access token using a valid refresh token.

    Returns 200 JSON ``{"success": true}`` and sets a fresh ``admin_access_token``
    cookie, or 401 if the refresh token is missing / invalid / expired.
    """
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        return jsonify({"error": "Refresh token missing"}), 401

    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return jsonify({"error": "Refresh token invalid or expired"}), 401

    new_access = generate_access_token()
    response = make_response(jsonify({"success": True}))

    import os

    secure = os.getenv("FLASK_ENV", "").strip().lower() == "production"
    from app.admin.auth import ACCESS_TOKEN_EXPIRES

    response.set_cookie(
        ACCESS_COOKIE,
        new_access,
        httponly=True,
        secure=secure,
        samesite="Lax",
        max_age=ACCESS_TOKEN_EXPIRES * 60,
        path="/",
    )
    return response
