"""
JWT-based authentication utilities for the admin module.

Token strategy
--------------
* **Access token** – short-lived (default 15 min), stored in an HTTP-only
  ``admin_access_token`` cookie.
* **Refresh token** – long-lived (default 7 days), stored in an HTTP-only
  ``admin_refresh_token`` cookie.

Both cookies use ``SameSite=Lax`` and, in production, ``Secure=True`` so they
are never transmitted over plain HTTP.

Environment variables
---------------------
JWT_SECRET_KEY                 Secret used to sign tokens (required in prod).
ACCESS_TOKEN_EXPIRES_MINUTES   Lifetime of access tokens (default: 15).
REFRESH_TOKEN_EXPIRES_DAYS     Lifetime of refresh tokens (default: 7).
ADMIN_USERNAME                 Admin login username (default: gramscs).
ADMIN_PASSWORD_HASH            Werkzeug-hashed password for the admin user.
"""

import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, jsonify, redirect, url_for, make_response
from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

_DEFAULT_JWT_SECRET = "jwt-dev-secret-gram-scs-2024"


def _resolve_jwt_secret() -> str:
    configured = os.environ.get("JWT_SECRET_KEY", "").strip()
    if configured and configured != _DEFAULT_JWT_SECRET:
        return configured

    flask_env = os.getenv("FLASK_ENV", "").strip().lower()
    if flask_env == "development":
        return _DEFAULT_JWT_SECRET

    # Runtime fallback prevents production boot warnings from surfacing as
    # critical errors while keeping token signing enabled.
    runtime_secret = secrets.token_urlsafe(48)
    logger.warning(
        "JWT_SECRET_KEY is not configured. Using a generated runtime secret. "
        "Admin tokens will be invalidated on restart."
    )
    return runtime_secret


JWT_SECRET: str = _resolve_jwt_secret()
ACCESS_TOKEN_EXPIRES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRES_MINUTES", 15))
REFRESH_TOKEN_EXPIRES: int = int(os.environ.get("REFRESH_TOKEN_EXPIRES_DAYS", 7))

ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "gramscs")
ADMIN_PASSWORD_HASH: str = os.environ.get("ADMIN_PASSWORD_HASH", "")

_flask_env = os.getenv("FLASK_ENV", "").strip().lower()

if _flask_env != "development" and JWT_SECRET == _DEFAULT_JWT_SECRET:
    logger.warning(
        "JWT_SECRET_KEY is using the development default in a non-development environment."
    )

if _flask_env != "development" and not ADMIN_PASSWORD_HASH:
    logger.warning(
        "ADMIN_PASSWORD_HASH is not set. Admin login is disabled for safety."
    )

# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"
ACCESS_COOKIE = "admin_access_token"
REFRESH_COOKIE = "admin_refresh_token"


def _build_payload(token_type: str, expires_delta: timedelta) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "sub": "admin",
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }


def generate_access_token() -> str:
    """Return a signed JWT access token."""
    payload = _build_payload("access", timedelta(minutes=ACCESS_TOKEN_EXPIRES))
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    """Return a signed JWT refresh token."""
    payload = _build_payload("refresh", timedelta(days=REFRESH_TOKEN_EXPIRES))
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


def verify_token(token: str, expected_type: str = "access") -> dict | None:
    """Decode *token* and return its payload, or ``None`` on any failure.

    Parameters
    ----------
    token:          Raw JWT string.
    expected_type:  ``"access"`` or ``"refresh"``.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT %s token has expired.", expected_type)
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid JWT token: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Credential check
# ---------------------------------------------------------------------------


def check_admin_credentials(username: str, password: str) -> bool:
    """Return ``True`` when *username* and *password* match the configured admin account.

    The password is verified against the Werkzeug-hashed value stored in
    ``ADMIN_PASSWORD_HASH``.  Login is refused if no hash is configured.
    """
    if not ADMIN_PASSWORD_HASH:
        logger.error("Admin login attempted but ADMIN_PASSWORD_HASH is not configured.")
        return False
    if username != ADMIN_USERNAME:
        return False
    return check_password_hash(ADMIN_PASSWORD_HASH, password)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _is_secure() -> bool:
    return os.getenv("FLASK_ENV", "").strip().lower() == "production"


def set_auth_cookies(response, *, access_token: str, refresh_token: str):
    """Attach access and refresh token HTTP-only cookies to *response*."""
    secure = _is_secure()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="Lax",
        max_age=ACCESS_TOKEN_EXPIRES * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="Lax",
        max_age=REFRESH_TOKEN_EXPIRES * 24 * 60 * 60,
        path="/admin/refresh",  # Scope refresh cookie to the refresh endpoint
    )
    return response


def clear_auth_cookies(response):
    """Delete both auth cookies from *response*."""
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/admin/refresh")
    return response


# ---------------------------------------------------------------------------
# Authentication decorator
# ---------------------------------------------------------------------------


def require_admin(f):
    """View decorator that enforces admin JWT authentication.

    1. Checks the ``admin_access_token`` cookie.
    2. If absent or expired, checks ``admin_refresh_token`` (auto-refresh).
    3. On failure, redirects HTML requests to ``/admin/login`` or returns
       a 401 JSON response for API/AJAX requests.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        access_token = request.cookies.get(ACCESS_COOKIE)
        payload = verify_token(access_token, "access") if access_token else None

        if payload:
            # Happy path – valid access token.
            return f(*args, **kwargs)

        # Access token missing or expired – try to refresh.
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        refresh_payload = verify_token(refresh_token, "refresh") if refresh_token else None

        if refresh_payload:
            # Issue a new access token and continue.
            new_access = generate_access_token()
            response = make_response(f(*args, **kwargs))
            secure = _is_secure()
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

        # Both tokens invalid – reject the request.
        wants_json = (
            request.path.startswith("/api/")
            or "application/json" in request.accept_mimetypes.best
        )
        if wants_json:
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for("admin.login"))

    return decorated
