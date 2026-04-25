import os
import logging

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = 'xk7m2p-dev-secret-key-gram-scs-2024'
_PROD_FALLBACK_SECRET = '982UVBcA5OF7MAEzwa72e0PZ5wOZlhJPWkgGfzmSSjc-VIGWvEqt3J_N133PWw2e'


def _resolve_secret_key() -> str:
    configured = os.environ.get("SECRET_KEY", "").strip()
    if configured and configured != _DEFAULT_SECRET:
        return configured

    flask_env = os.getenv('FLASK_ENV', '').strip().lower()
    if flask_env == 'development':
        return _DEFAULT_SECRET

    # In non-development environments, use a stable fallback secret so
    # sessions continue to work across restarts even without env configuration.
    logger.warning(
        "SECRET_KEY is not configured. Using built-in fallback secret."
    )
    return _PROD_FALLBACK_SECRET


SECRET_KEY = _resolve_secret_key()

_flask_env = os.getenv('FLASK_ENV', '').strip().lower()
if _flask_env != 'development' and SECRET_KEY == _DEFAULT_SECRET:
    logger.warning(
        "SECRET_KEY is using the development default in a non-development environment."
    )

# JWT_SECRET_KEY is validated separately in app/admin/auth.py when that module is loaded.