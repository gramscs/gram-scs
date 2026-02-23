from flask import Blueprint, render_template, abort
from app import cache

pages_bp = Blueprint(
    "pages",
    __name__,
    template_folder="templates"
)

@pages_bp.route("/<page>")
@cache.cached(timeout=300)
def show_page(page):
    try:
        return render_template(f"pages/{page}.html")
    except Exception as e:
        print(e)
        abort(404)
