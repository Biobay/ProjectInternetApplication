from datetime import datetime

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from ..extensions import db
from ..models import Tournament, TournamentParticipant, Match


users_bp = Blueprint("users", __name__, template_folder="../templates/users")


@users_bp.get("/")
@login_required
def dashboard():
    # Tournaments where the current user is registered as a participant
    upcoming_tournaments = (
        db.session.query(Tournament)
        .join(TournamentParticipant)
        .filter(TournamentParticipant.user_id == current_user.id)
        .order_by(Tournament.start_at.asc())
        .all()
    )

    # Matches where the current user is one of the players and the match has no winner yet.
    # We also require both player slots to be filled so that we only show
    # matches that actually require the user's attention (no byes).
    upcoming_matches = (
        Match.query.filter(
            Match.winner_id.is_(None),
            Match.player_a_id.isnot(None),
            Match.player_b_id.isnot(None),
            or_(
                Match.player_a.has(TournamentParticipant.user_id == current_user.id),
                Match.player_b.has(TournamentParticipant.user_id == current_user.id),
            ),
        )
        .order_by(Match.round_number.asc(), Match.bracket_position.asc())
        .all()
    )

    # For nicer labels like "Quarti di finale" / "Semifinale" / "Finale",
    # compute the maximum round number per tournament for the matches that
    # involve the current user.
    max_rounds_by_tournament: dict[int, int] = {}
    tournament_ids = {m.tournament_id for m in upcoming_matches}
    if tournament_ids:
        rows = (
            db.session.query(Match.tournament_id, func.max(Match.round_number))
            .filter(Match.tournament_id.in_(tournament_ids))
            .group_by(Match.tournament_id)
            .all()
        )
        max_rounds_by_tournament = {tid: max_round for tid, max_round in rows}

    # Current time used in the template to derive human-friendly
    # tournament status labels (es. "Iscrizioni aperte", "In corso").
    now = datetime.utcnow()

    return render_template(
        "users/dashboard.html",
        upcoming_matches=upcoming_matches,
        upcoming_tournaments=upcoming_tournaments,
        max_rounds_by_tournament=max_rounds_by_tournament,
        now=now,
    )
