from flask import Blueprint, render_template

users_bp = Blueprint("users", __name__, template_folder="../templates/users")


@users_bp.get("/")
def dashboard():
    return render_template(
        "users/dashboard.html",
        upcoming_matches=[],
        upcoming_tournaments=[],
    )
