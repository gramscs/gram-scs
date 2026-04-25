import os
import logging
import secrets

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = 'xk7m2p-dev-secret-key-gram-scs-2024'


def _resolve_secret_key() -> str:
    configured = os.environ.get("SECRET_KEY", "").strip()
    if configured and configured != _DEFAULT_SECRET:
        return configured

    flask_env = os.getenv('FLASK_ENV', '').strip().lower()
    if flask_env == 'development':
        return _DEFAULT_SECRET

    # In non-development environments, use an in-memory secret fallback
    # to avoid boot-time failures when SECRET_KEY is not configured.
    runtime_secret = secrets.token_urlsafe(48)
    logger.warning(
        "SECRET_KEY is not configured. Using a generated runtime secret. "
        "Sessions may be invalidated on restart."
    )
    return runtime_secret


SECRET_KEY = _resolve_secret_key()

_flask_env = os.getenv('FLASK_ENV', '').strip().lower()
if _flask_env != 'development' and SECRET_KEY == _DEFAULT_SECRET:
    logger.warning(
        "SECRET_KEY is using the development default in a non-development environment."
    )

# JWT_SECRET_KEY is validated separately in app/admin/auth.py when that module is loaded.