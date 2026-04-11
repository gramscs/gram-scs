from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__
)

# Auth routes (login / logout / refresh) must be imported after admin_bp is created
from app.admin import auth_routes  # noqa: E402, F401  (side-effect import)

