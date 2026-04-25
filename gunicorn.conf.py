import multiprocessing
import os


port = os.getenv("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Ensure availability even when one request (for example /health/db) is waiting on DB.
default_workers = max(2, (multiprocessing.cpu_count() * 2) + 1)
workers = int(os.getenv("WEB_CONCURRENCY", str(default_workers)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

# Keep requests from hanging forever at the worker level.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "90"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Log to stdout/stderr for Render log collection.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
