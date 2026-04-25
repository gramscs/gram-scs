"""
Session-based authentication utilities for the admin module.

Environment variables
---------------------
SECRET_KEY           Flask session signing key (required by app config).
ADMIN_USERNAME       Admin login username (default: admin).
ADMIN_PASSWORD_HASH  Werkzeug-hashed password for the admin user (required).
"""

import os
from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

ADMIN_USERNAME: str = (os.environ.get("ADMIN_USERNAME") or "admin").strip() or "admin"
ADMIN_PASSWORD_HASH: str = (os.environ.get("ADMIN_PASSWORD_HASH") or "").strip()

if not ADMIN_PASSWORD_HASH:
    raise RuntimeError("ADMIN_PASSWORD_HASH is required and must be set in environment variables.")

ADMIN_SESSION_KEY = "admin_authenticated"


def check_admin_credentials(username: str, password: str) -> bool:
    """Return True when username and password match configured admin credentials."""
    return username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password)


def login_admin() -> None:
    """Mark the current session as authenticated admin."""
    session[ADMIN_SESSION_KEY] = True


def logout_admin() -> None:
    """Clear admin authentication state from session."""
    session.pop(ADMIN_SESSION_KEY, None)


def is_admin_authenticated() -> bool:
    """Return True when current session is authenticated as admin."""
    return bool(session.get(ADMIN_SESSION_KEY))


def require_admin(f):
    """View decorator that enforces admin session authentication."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if is_admin_authenticated():
            return f(*args, **kwargs)

        wants_json = (
            request.path.startswith("/api/")
            or "application/json" in (request.accept_mimetypes.best or "")
            or (request.content_type or "").startswith("application/json")
        )
        if wants_json:
            return jsonify({"error": "Authentication required"}), 401

        return redirect(url_for("admin.login"))

    return decorated
