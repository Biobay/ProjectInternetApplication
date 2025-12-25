from flask import Blueprint, flash, redirect, render_template, request, url_for

matches_bp = Blueprint("matches", __name__, template_folder="../templates/matches")


@matches_bp.get("/<int:match_id>")
def view_match(match_id: int):
    return render_template("matches/detail.html", match_id=match_id)


@matches_bp.route("/<int:match_id>/report", methods=["POST"])
def report_result(match_id: int):
    winner = request.form.get("winner")
    flash(f"Result submission placeholder winner={winner}", "info")
    return redirect(url_for("matches.view_match", match_id=match_id))
