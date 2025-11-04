from flask import Blueprint, render_template
from .feature_flags import require_flag

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/beta")
@require_flag("beta_page", default=False, status_code=404)
def beta():
    return render_template("beta.html")

