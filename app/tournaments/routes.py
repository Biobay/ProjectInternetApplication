from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..config import BaseConfig


_tournaments_per_page = BaseConfig.TOURNAMENTS_PER_PAGE

tournaments_bp = Blueprint("tournaments", __name__, template_folder="../templates/tournaments")


@tournaments_bp.get("/")
def list_tournaments():
    page = int(request.args.get("page", 1))
    return render_template(
        "tournaments/list.html",
        tournaments=[],
        page=page,
        per_page=_tournaments_per_page,
    )


@tournaments_bp.get("/<int:tournament_id>")
def details(tournament_id: int):
    return render_template("tournaments/detail.html", tournament_id=tournament_id)


@tournaments_bp.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        flash("Tournament creation flow not implemented yet", "warning")
        return redirect(url_for("tournaments.list_tournaments"))
    return render_template("tournaments/create.html")
