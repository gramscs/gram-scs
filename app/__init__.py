import os
from flask import Flask, send_from_directory, request
from .models import db
from cachelib import FileSystemCache
from functools import wraps
import hashlib
import json


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

                except RuntimeError:
                    return func(*args, **kwargs)

            return wrapped
        return decorator


# cache instance
cache = CacheShim()


def create_app():
    app = Flask(__name__)

    # DATABASE CONFIG
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    return app