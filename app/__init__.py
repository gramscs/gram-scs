from flask import Flask, send_from_directory, request, render_template, jsonify, Response
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:
    def get_remote_address():
        return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')

    class Limiter:
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, app):
            return app

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator
from .models import db
from cachelib import FileSystemCache
from functools import wraps
import hashlib
import importlib
import os
import logging
from pathlib import Path
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from app.db_maintenance import ensure_consignment_columns_async
from importlib import metadata as importlib_metadata

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').strip().upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    importlib_metadata.version('werkzeug')
except Exception:
    _original_metadata_version = importlib_metadata.version

    def _metadata_version(name):
        if name == 'werkzeug':
            try:
                import werkzeug
                return getattr(werkzeug, '__version__', '3.1.6')
            except Exception:
                return '3.1.6'
        return _original_metadata_version(name)

    importlib_metadata.version = _metadata_version


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

    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url or database_url.startswith('sqlite://'):
        return True

    return _env_bool('AUTO_CREATE_TABLES', default=True)


def _default_local_sqlite_uri():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    instance_dir = os.path.join(repo_root, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    database_path = os.path.join(instance_dir, 'dev.db')
    return f'sqlite:///{database_path}'


def _normalize_sqlite_database_uri(database_uri):
    if not database_uri or not database_uri.startswith('sqlite:///'):
        return database_uri

    database_path = database_uri[len('sqlite:///'):]
    if not database_path:
        return database_uri

    if database_path.startswith('/'):
        return database_uri

    repo_root = Path(__file__).resolve().parent.parent
    resolved_path = (repo_root / database_path).resolve()
    return f'sqlite:///{resolved_path}'


def _ensure_sqlite_parent_directory(database_uri):
    if not database_uri or not database_uri.startswith('sqlite:///'):
        return

    database_path = database_uri[len('sqlite:///'):]
    if not database_path:
        return

    sqlite_path = Path(database_path)
    if not sqlite_path.is_absolute():
        repo_root = Path(__file__).resolve().parent.parent
        sqlite_path = (repo_root / sqlite_path).resolve()

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)


if _should_load_local_env_files():
    _load_env_file('.env.local')
    _load_env_file('.env')


def _require_database_uri():
    """Require a PostgreSQL DATABASE_URL for production, allow SQLite in development."""
    raw_uri = os.getenv('DATABASE_URL', '').strip()
    if not raw_uri:
        if os.getenv('FLASK_ENV', '').strip().lower() == 'production':
            raise RuntimeError('DATABASE_URL is required in production.')

        logger.warning('DATABASE_URL is not set; using local SQLite fallback for development.')
        return _default_local_sqlite_uri()

    if raw_uri.startswith('sqlite://'):
        if os.getenv('FLASK_ENV', '').strip().lower() != 'production':
            return raw_uri
        raise RuntimeError('SQLite is only supported for development testing.')

    raw_uri = _normalize_postgres_uri(raw_uri)

    if not raw_uri.startswith('postgresql://'):
        raise RuntimeError('DATABASE_URL must be a PostgreSQL URL (postgresql://...).')

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


def _postgres_driver_is_available():
    try:
        importlib.import_module('psycopg2')
    except Exception as exc:
        logger.warning('PostgreSQL driver is unavailable: %s', exc)
        return False
    return True


def _seed_development_consignment_data():
    if os.getenv('FLASK_ENV', '').strip().lower() != 'development':
        return

    from app.models import Consignment

    try:
        # If the DB already has 100 or more consignments, do nothing.
        existing_count = Consignment.query.count()
        if existing_count >= 100:
            return

        # Build deterministic sample consignments and avoid duplicates.
        sample_consignment_data = []
        statuses = ['Pickup Scheduled', 'In Transit', 'Out for Delivery', 'Delivered']
        existing_numbers = {row[0] for row in Consignment.query.with_entities(Consignment.consignment_number).all()}

        for i in range(1, 101):
            cn = f"DEV{str(i).zfill(4)}"
            if cn in existing_numbers:
                continue

            status = statuses[i % len(statuses)]
            pickup_pincode = str(110000 + (i % 900000))[:6]
            drop_pincode = str(400000 + (i % 500000))[:6]
            pickup_address = f"{i} Dev Pickup St, Dev City {i % 10}"
            drop_address = f"{i} Dev Drop Ave, Dest City {i % 10}"
            pickup_date = f"2026-05-{(i % 28) + 1:02d}"
            drop_date = f"2026-06-{(i % 28) + 1:02d}"
            eta = f"2026-06-{(i % 28) + 1:02d} 12:00"

            sample_consignment_data.append(
                Consignment(
                    consignment_number=cn,
                    status=status,
                    pickup_address=pickup_address,
                    pickup_pincode=pickup_pincode,
                    pickup_date=pickup_date,
                    drop_address=drop_address,
                    drop_pincode=drop_pincode,
                    drop_date=drop_date,
                    eta=eta,
                    pickup_tag=f"PICK{i % 5}",
                    drop_tag=f"DROP{i % 7}",
                )
            )

        # Only add as many rows as necessary to reach 100 total.
        to_add = []
        remaining = max(0, 100 - existing_count)
        for item in sample_consignment_data:
            if remaining <= 0:
                break
            to_add.append(item)
            remaining -= 1

        if to_add:
            db.session.add_all(to_add)
            db.session.commit()

        logger.info('Seeded development consignments; total now %d (added %d)', Consignment.query.count(), len(to_add))
    except Exception as e:
        db.session.rollback()
        logger.exception('Failed to seed development consignments: %s', e)


def _build_content_security_policy():
    return (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'self'; "
        "form-action 'self'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "connect-src 'self'; "
        "frame-src 'self' https://www.google.com https://maps.google.com;"
    )


def _apply_security_headers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        )
        response.headers.setdefault('Content-Security-Policy', _build_content_security_policy())

        if request.is_secure or request.headers.get('X-Forwarded-Proto', '').lower() == 'https':
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains'
            )

        return response


def create_app():
    app = Flask(__name__)
    # Log effective PORT so platform startup probes can be debugged in deployment logs.
    try:
        effective_port = os.getenv('PORT', '10000')
        logger.info('STARTUP: effective PORT=%s', effective_port)
    except Exception:
        logger.exception('Failed to log STARTUP port')

    # DATABASE CONFIG
    db_uri = _normalize_sqlite_database_uri(_require_database_uri())
    if (
        db_uri.startswith('postgresql://')
        and os.getenv('FLASK_ENV', '').strip().lower() != 'production'
        and not _postgres_driver_is_available()
    ):
        logger.warning('Falling back to local SQLite because PostgreSQL driver could not be loaded.')
        db_uri = _default_local_sqlite_uri()

    if db_uri.startswith('sqlite://'):
        _ensure_sqlite_parent_directory(db_uri)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = _env_bool(
        'SESSION_COOKIE_SECURE',
        default=os.getenv('FLASK_ENV', '').strip().lower() == 'production'
    )
    app.config['PREFERRED_URL_SCHEME'] = 'https' if os.getenv('FLASK_ENV', '').strip().lower() == 'production' else 'http'

    if db_uri.startswith('sqlite://'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': False,
        }
    else:
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

    auto_create_tables = _should_auto_create_tables()
    if auto_create_tables:
        try:
            if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite://'):
                ensure_consignment_columns_async(app.config['SQLALCHEMY_DATABASE_URI'], logger)
        except Exception as exc:
            logger.warning('Failed to start consignment schema repair: %s', exc)

        with app.app_context():
            db.create_all()
            _seed_development_consignment_data()
    else:
        try:
            if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite://'):
                ensure_consignment_columns_async(app.config['SQLALCHEMY_DATABASE_URI'], logger)
        except Exception as exc:
            logger.warning('Failed to start consignment schema repair: %s', exc)

        logger.info('AUTO_CREATE_TABLES disabled. Skipping db.create_all() at startup.')
        logger.info('Consignment schema repair runs asynchronously in production.')

    from app.frontend.routes.main.routes import main_bp
    from app.frontend.routes.track.routes import track_bp
    from app.frontend.routes.pages.routes import pages_bp
    from app.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(track_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(admin_bp)
    _apply_security_headers(app)

    @app.route('/health')
    def health():
        return jsonify({
            'status': 'ok',
            'message': 'Application is healthy',
        }), 200

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
