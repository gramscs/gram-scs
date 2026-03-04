import os
from flask import Flask, send_from_directory, request, render_template, jsonify
from .models import db
from cachelib import FileSystemCache
from functools import wraps
import hashlib
import json
from flask_mail import Mail
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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

mail = Mail()
def create_app():
    app = Flask(__name__)

    # DATABASE CONFIG
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config.from_object('app.config')

    mail.init_app(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    from app.main.routes import main_bp
    from app.pages.routes import pages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(pages_bp)

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

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
            return jsonify({'error': 'An unexpected error occurred'}), 500
        return render_template('errors/500.html'), 500

    return app