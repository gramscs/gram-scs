from flask import Flask, send_from_directory, request
from cachelib import FileSystemCache
from functools import wraps
import hashlib
import json

# Simple cache shim exposing `cached(timeout=...)` decorator.
class CacheShim:
    def __init__(self, cache_dir='flask_cache', default_timeout=300):
        self._cache = FileSystemCache(cache_dir)
        self.default_timeout = default_timeout

    def _make_key(self, *args, **kwargs):
        # Use request path + query string to key cache per URL
        key = request.path + ('?' + request.query_string.decode() if request.query_string else '')
        return hashlib.sha1(key.encode('utf-8')).hexdigest()

    def cached(self, timeout=None):
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                try:
                    cache_key = self._make_key()
                    cached_val = self._cache.get(cache_key)
                    if cached_val is not None:
                        return json.loads(cached_val)
                    result = func(*args, **kwargs)
                    # only cache string responses (render_template returns Markup/str)
                    try:
                        dump = json.dumps(result)
                    except Exception:
                        # fallback: store as string
                        dump = json.dumps(str(result))
                    self._cache.set(cache_key, dump, timeout or self.default_timeout)
                    # original result may be a Response or str; attempt to return original type
                    return result
                except RuntimeError:
                    # if no request context, just call through
                    return func(*args, **kwargs)
            return wrapped
        return decorator

# cache instance (shim)
cache = CacheShim()


def create_app():
    app = Flask(__name__)

    from app.main.routes import main_bp
    from app.pages.routes import pages_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(pages_bp)

    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.ico')

    return app
