import os

SECRET_KEY = os.environ.get("SECRET_KEY") or 'xk7m2p-dev-secret-key-gram-scs-2024'

MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")