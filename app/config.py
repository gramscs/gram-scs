import os
import logging

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = 'xk7m2p-dev-secret-key-gram-scs-2024'
SECRET_KEY = os.environ.get("SECRET_KEY") or _DEFAULT_SECRET

_flask_env = os.getenv('FLASK_ENV', '').strip().lower()
if _flask_env != 'development' and SECRET_KEY == _DEFAULT_SECRET:
    logger.critical(
        "SECURITY WARNING: SECRET_KEY is not set or is still the default dev value. "
        "Set a unique SECRET_KEY in your Render environment variables to protect user sessions."
    )

# JWT_SECRET_KEY is validated separately in app/admin/auth.py when that module is loaded.