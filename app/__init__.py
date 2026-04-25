from flask import Flask, send_from_directory, request, render_template, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .models import db
from cachelib import FileSystemCache
from functools import wraps
import hashlib
import os
import logging
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').strip().upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _resolve_rate_limit_storage_uri():
    configured = os.getenv('RATELIMIT_STORAGE_URI', '').strip()
    if configured:
        return configured

    redis_url = os.getenv('REDIS_URL', '').strip()
    if redis_url:
        return redis_url

    return 'memory://'


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s: %s. Using default %s", name, raw, default)
        return default


# Simple cache shim exposing `cached(timeout=...)` decorator.
class CacheShim:
    def __init__(self, cache_dir='flask_cache', default_timeout=300):
        self._cache = FileSystemCache(cache_dir)
        self.default_timeout = default_timeout

    def _make_key(self):
        key = request.path
        if request.query_string:
            key += '?' + request.query_string.decode()
        return hashlib.sha1(key.encode('utf-8')).hexdigest()

    def cached(self, timeout=None):
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                try:
                    cache_key = self._make_key()
                    cached_val = self._cache.get(cache_key)
                    if cached_val is not None:
                        return cached_val

                    result = func(*args, **kwargs)
                    self._cache.set(cache_key, result, timeout or self.default_timeout)
                    return result

                except Exception as e:
                    logger.error(f"Cache error: {e}")
                    return func(*args, **kwargs)

            return wrapped
        return decorator


# cache instance
cache = CacheShim()

# limiter instance shared across the application
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=_resolve_rate_limit_storage_uri(),
)

def _load_env_file(path):
    """Load simple KEY=VALUE pairs from a local env file if it exists."""
    if not os.path.exists(path):
        return

    with open(path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[len('export '):].strip()
            if '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def _should_load_local_env_files():
    # Render injects env vars directly; avoid reading local files in production by default.
    if _env_bool('LOAD_LOCAL_ENV_FILES', False):
        return True
    return os.getenv('FLASK_ENV', '').strip().lower() != 'production'


def _should_auto_create_tables():
    if os.getenv('FLASK_ENV', '').strip().lower() == 'production':
        if _env_bool('AUTO_CREATE_TABLES', False):
            logger.warning('Ignoring AUTO_CREATE_TABLES in production; manage schema externally.')
        return False

    return _env_bool('AUTO_CREATE_TABLES', default=True)


if _should_load_local_env_files():
    _load_env_file('.env.local')
    _load_env_file('.env')


def _require_database_uri():
    """Require a PostgreSQL DATABASE_URL for all environments."""
    raw_uri = os.getenv('DATABASE_URL', '').strip()
    if not raw_uri:
        raise RuntimeError('DATABASE_URL is required. SQLite is no longer supported.')

    raw_uri = _normalize_postgres_uri(raw_uri)

    if not raw_uri.startswith('postgresql://'):
        raise RuntimeError('DATABASE_URL must be a PostgreSQL URL (postgresql://...).')

    return raw_uri


def _resolve_master_database_uri():
    """Resolve the ETA master database URL, defaulting to the main database locally."""
    raw_uri = os.getenv('MASTER_DATABASE_URL', '').strip() or _require_database_uri()

    raw_uri = _normalize_postgres_uri(raw_uri)

    if not raw_uri.startswith('postgresql://'):
        raise RuntimeError('MASTER_DATABASE_URL must be a PostgreSQL URL (postgresql://...).')

    return raw_uri


def _normalize_postgres_uri(raw_uri):
    """Normalize postgres URIs and enforce SSL for Supabase hosts."""
    # Some platforms expose postgres:// which SQLAlchemy does not accept.
    if raw_uri.startswith('postgres://'):
        raw_uri = raw_uri.replace('postgres://', 'postgresql://', 1)

    parsed = urlparse(raw_uri)
    hostname = (parsed.hostname or '').lower()

    if 'supabase.com' in hostname:
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_params.setdefault('sslmode', 'require')
        parsed = parsed._replace(query=urlencode(query_params))
        raw_uri = urlunparse(parsed)

    return raw_uri


def create_app():
    app = Flask(__name__)

    # DATABASE CONFIG
    app.config['SQLALCHEMY_DATABASE_URI'] = _require_database_uri()
    app.config['SQLALCHEMY_BINDS'] = {
        'master': _resolve_master_database_uri(),
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        # Supabase/Render-safe defaults; overridable via env vars.
        'pool_pre_ping': _env_bool('DB_POOL_PRE_PING', True),
        'pool_recycle': _env_int('DB_POOL_RECYCLE', 180),
        'pool_size': _env_int('DB_POOL_SIZE', 3),
        'max_overflow': _env_int('DB_MAX_OVERFLOW', 2),
        'pool_timeout': _env_int('DB_POOL_TIMEOUT', 30),
        'connect_args': {
            'connect_timeout': _env_int('DB_CONNECT_TIMEOUT', 10),
        },
    }
    app.config['RATELIMIT_STORAGE_URI'] = _resolve_rate_limit_storage_uri()
    app.config['RATELIMIT_HEADERS_ENABLED'] = True
    app.config.from_object('app.config')

    db.init_app(app)
    limiter.init_app(app)

    from app.eta_master.models import EtaMasterRecord

    auto_create_tables = _should_auto_create_tables()
    if auto_create_tables:
        with app.app_context():
            db.create_all()
    else:
        logger.info('AUTO_CREATE_TABLES disabled. Skipping db.create_all() at startup.')

    from app.main.routes import main_bp
    from app.track.routes import track_bp
    from app.eta_master.routes import eta_master_bp
    from app.pages.routes import pages_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(track_bp)
    app.register_blueprint(eta_master_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)

    @app.route('/health/db')
    def database_health():
        try:
            db.session.execute(text('SELECT 1'))
            return jsonify({
                'status': 'ok',
                'database': 'postgresql',
                'message': 'Database connection is healthy',
            }), 200
        except Exception as e:
            logger.error('Database health check failed: %s', e)
            return jsonify({
                'status': 'error',
                'database': 'postgresql',
                'message': 'Database connection failed',
            }), 503

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.ico')

    # Global error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        logger.warning(f"404 error: {request.url}")
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"500 error: {e}")
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        logger.warning(f"403 error: {request.url}")
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Access forbidden'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(429)
    def rate_limited(e):
        logger.warning(
            'Rate limit exceeded for %s %s from %s',
            request.method,
            request.path,
            request.headers.get('X-Forwarded-For', request.remote_addr),
        )

        message = 'Too many requests. Please try again later.'
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json or request.is_json:
            response = jsonify({'error': message})
            response.status_code = 429
            return response

        return Response(message, status=429, mimetype='text/plain')

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'An unexpected error occurred'}), 500
        return render_template('errors/500.html'), 500

    return app