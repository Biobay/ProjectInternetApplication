from datetime import datetime

from flask import Blueprint, current_app, render_template, request

from ..models import Tournament


core_bp = Blueprint("core", __name__)


@core_bp.get("/")
def index():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config.get("TOURNAMENTS_PER_PAGE", 10)

    query = (
        Tournament.query.filter(Tournament.start_at >= datetime.utcnow())
        .order_by(Tournament.start_at.asc())
    )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "index.html",
        tournaments=pagination.items,
        page=pagination.page,
        per_page=per_page,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_page=pagination.next_num,
        prev_page=pagination.prev_num,
        total=pagination.total,
    )
