from datetime import datetime
import re
from typing import Optional

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Tournament, TournamentParticipant, Match
from .forms import TournamentForm, TournamentApplicationForm


tournaments_bp = Blueprint(
    "tournaments", __name__, template_folder="../templates/tournaments"
)


def _normalize_google_maps_input(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    text = raw.strip()
    # Se l'utente incolla l'intero iframe, estraiamo l'URL dal src="..."
    match = re.search(r'src=["\']([^"\']+)["\']', text)
    if match:
        return match.group(1)
    return text or None


def _ensure_round1_bracket(tournament_id: int, *, ignore_deadline: bool = False) -> bool:
    """Generate round 1 matches.

    By default it only runs after the signup deadline; when
    ``ignore_deadline`` is True, it generates immediately (used by
    the organizer's "Generate bracket now" button).
    Returns True if matches were created, False otherwise.
    """
    now = datetime.utcnow()
    locked_tournament = (
        Tournament.query.with_for_update().filter_by(id=tournament_id).first()
    )
    if not locked_tournament:
        return False

    # Solo dopo la deadline iscrizioni, a meno che non sia una forzatura
    if not ignore_deadline and locked_tournament.signup_deadline > now:
        return False

    # Se ci sono già match di round 1, non rigenerare
    existing = (
        Match.query.filter_by(
            tournament_id=locked_tournament.id, round_number=1
        ).count()
    )
    if existing > 0:
        return False

    participants = (
        TournamentParticipant.query.filter_by(tournament_id=locked_tournament.id)
        .order_by(TournamentParticipant.ranking.asc())
        .all()
    )

    if len(participants) < 2:
        return False

    # Seeding: 1 vs ultimo, 2 vs penultimo, ...
    left = 0
    right = len(participants) - 1
    bracket_position = 1
    while left < right:
        player_a = participants[left]
        player_b = participants[right]
        match = Match(
            tournament_id=locked_tournament.id,
            round_number=1,
            bracket_position=bracket_position,
            player_a_id=player_a.id,
            player_b_id=player_b.id,
        )
        db.session.add(match)
        left += 1
        right -= 1
        bracket_position += 1

    # Se numero dispari di giocatori: ultimo rimasto prende un bye
    if left == right:
        player_a = participants[left]
        match = Match(
            tournament_id=locked_tournament.id,
            round_number=1,
            bracket_position=bracket_position,
            player_a_id=player_a.id,
            player_b_id=None,
        )
        db.session.add(match)
    db.session.commit()
    return True


def _advance_winner(match: Match) -> None:
    """Advance the winner of a match to the appropriate next-round match.

    Uses the tournament, round_number and bracket_position to determine the
    next match. If the next-round match does not exist yet, it is created
    with empty player slots and the winner is placed into the correct slot.
    """
    if not match.winner_id:
        return

    # Determine next round and bracket position
    next_round = match.round_number + 1
    # Example: match positions 1 and 2 feed into position 1 of next round,
    # positions 3 and 4 feed into position 2, etc.
    next_bracket_position = (match.bracket_position + 1) // 2

    next_match = (
        Match.query.filter_by(
            tournament_id=match.tournament_id,
            round_number=next_round,
            bracket_position=next_bracket_position,
        ).first()
    )

    if not next_match:
        next_match = Match(
            tournament_id=match.tournament_id,
            round_number=next_round,
            bracket_position=next_bracket_position,
        )
        db.session.add(next_match)

    # Decide whether the winner goes into player_a or player_b slot in next match
    if match.bracket_position % 2 == 1:
        # Left child feeds player A
        if next_match.player_a_id is None:
            next_match.player_a_id = match.winner_id
    else:
        # Right child feeds player B
        if next_match.player_b_id is None:
            next_match.player_b_id = match.winner_id


@tournaments_bp.get("/")
def list_tournaments():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()
    per_page = current_app.config.get("TOURNAMENTS_PER_PAGE", 10)

    query = (
        Tournament.query.filter(Tournament.start_at >= datetime.utcnow())
        .order_by(Tournament.start_at.asc())
    )

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Tournament.name.ilike(like),
                Tournament.discipline.ilike(like),
                Tournament.description.ilike(like),
            )
        )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "tournaments/list.html",
        tournaments=pagination.items,
        page=pagination.page,
        per_page=per_page,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_page=pagination.next_num,
        prev_page=pagination.prev_num,
        q=q,
        total=pagination.total,
    )


@tournaments_bp.route("/<int:tournament_id>", methods=["GET", "POST"])
def details(tournament_id: int):
    tournament = Tournament.query.get_or_404(tournament_id)
    application_form = None
    is_organizer = False
    is_already_participant = False

    if current_user.is_authenticated:
        is_organizer = tournament.organizer_id == current_user.id
        existing = TournamentParticipant.query.filter_by(
            tournament_id=tournament.id, user_id=current_user.id
        ).first()
        is_already_participant = existing is not None

        if not is_organizer and not is_already_participant:
            application_form = TournamentApplicationForm()
            if application_form.validate_on_submit():
                # Controllo concorrenza + requisito 6 (max partecipanti)
                try:
                    locked_tournament = (
                        Tournament.query.with_for_update()
                        .filter_by(id=tournament_id)
                        .first()
                    )
                    if not locked_tournament:
                        flash("Tournament not found.", "danger")
                        return redirect(url_for("tournaments.list_tournaments"))

                    # Controllo deadline iscrizioni
                    if locked_tournament.signup_deadline <= datetime.utcnow():
                        flash("Signup deadline has passed.", "warning")
                        return redirect(
                            url_for(
                                "tournaments.details", tournament_id=locked_tournament.id
                            )
                        )

                    current_count = (
                        db.session.query(func.count(TournamentParticipant.id))
                        .filter_by(tournament_id=locked_tournament.id)
                        .scalar()
                    )

                    if current_count >= locked_tournament.max_participants:
                        flash("The tournament is full.", "warning")
                        return redirect(
                            url_for(
                                "tournaments.details", tournament_id=locked_tournament.id
                            )
                        )

                    participant = TournamentParticipant(
                        tournament_id=locked_tournament.id,
                        user_id=current_user.id,
                        license_number=application_form.license_number.data,
                        ranking=application_form.ranking.data,
                        status="pending",
                    )
                    db.session.add(participant)
                    db.session.commit()
                    flash("Application submitted.", "success")
                    return redirect(
                        url_for("tournaments.details", tournament_id=tournament_id)
                    )
                except IntegrityError:
                    db.session.rollback()
                    flash(
                        "Your license number or ranking is already used in this tournament.",
                        "danger",
                    )
                    return redirect(
                        url_for("tournaments.details", tournament_id=tournament_id)
                    )
        elif request.method == "POST":
            flash("You cannot apply to this tournament.", "warning")
            return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    # Dopo la deadline, genera il tabellone di round 1 se non esiste ancora
    if datetime.utcnow() > tournament.signup_deadline:
        _ensure_round1_bracket(tournament.id)

    participants = (
        TournamentParticipant.query.filter_by(tournament_id=tournament.id)
        .order_by(TournamentParticipant.ranking.asc())
        .all()
    )

    ranked_players_count = len(
        [p for p in participants if p.ranking is not None]
    )

    # Collect matches grouped by round so that the bracket (including
    # later rounds populated by advancing winners) can be shown.
    matches_by_round = {}
    max_round = (
        db.session.query(func.max(Match.round_number))
        .filter_by(tournament_id=tournament.id)
        .scalar()
    ) or 0

    for round_number in range(1, max_round + 1):
        matches_by_round[round_number] = (
            Match.query.filter_by(tournament_id=tournament.id, round_number=round_number)
            .order_by(Match.bracket_position.asc())
            .all()
        )

    return render_template(
        "tournaments/detail.html",
        tournament=tournament,
        application_form=application_form,
        is_organizer=is_organizer,
        is_already_participant=is_already_participant,
        ranked_players_count=ranked_players_count,
        participants=participants,
        matches_by_round=matches_by_round,
    )


@tournaments_bp.post("/matches/<int:match_id>/report")
@login_required
def report_match_result(match_id: int):
    """Allow one of the two players to report a match result.

    Double-confirmation logic:
    - Each player can declare who won (one of the two participants).
    - When both declarations are present and identical, winner_id is set.
    - If they differ, both declarations are cleared and players must resubmit.
    """
    match = Match.query.get_or_404(match_id)

    if match.winner_id is not None:
        flash("Result already confirmed for this match.", "info")
        return redirect(url_for("tournaments.details", tournament_id=match.tournament_id))

    # Ensure current user is one of the players
    player_a = match.player_a
    player_b = match.player_b

    if not player_a or not player_b:
        flash("This match cannot be reported (bye or incomplete pairing).", "warning")
        return redirect(url_for("tournaments.details", tournament_id=match.tournament_id))

    if current_user.id not in {player_a.user_id, player_b.user_id}:
        flash("You are not a participant in this match.", "danger")
        return redirect(url_for("tournaments.details", tournament_id=match.tournament_id))

    winner_id_raw = request.form.get("winner_id")
    if not winner_id_raw:
        abort(400)

    try:
        declared_winner_id = int(winner_id_raw)
    except ValueError:
        abort(400)

    if declared_winner_id not in {player_a.id, player_b.id}:
        abort(400)

    # Store declaration depending on which player is reporting
    if current_user.id == player_a.user_id:
        match.player_a_reported_winner_id = declared_winner_id
    elif current_user.id == player_b.user_id:
        match.player_b_reported_winner_id = declared_winner_id

    # Check if both players have reported
    a_report = match.player_a_reported_winner_id
    b_report = match.player_b_reported_winner_id

    if a_report and b_report:
        if a_report == b_report:
            match.winner_id = a_report
            _advance_winner(match)
            flash("Result confirmed by both players.", "success")
        else:
            # Conflict: reset and require new submissions
            match.player_a_reported_winner_id = None
            match.player_b_reported_winner_id = None
            flash(
                "Conflict between players' reports. Please agree on the result and submit again.",
                "danger",
            )
    else:
        flash("Your result has been recorded. Waiting for the other player.", "info")

    db.session.commit()
    return redirect(url_for("tournaments.details", tournament_id=match.tournament_id))


@tournaments_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = TournamentForm()
    if form.validate_on_submit():
        # basic protection against mass-assignment: map only allowed fields
        sponsor_assets = None
        if form.sponsor_logos.data:
            urls = [
                line.strip()
                for line in form.sponsor_logos.data.splitlines()
                if line.strip()
            ]
            sponsor_assets = {"logos": urls}

        google_maps_url = _normalize_google_maps_input(form.google_maps_url.data)

        tournament = Tournament(
            organizer_id=current_user.id,
            name=form.name.data,
            discipline=form.discipline.data,
            description=form.description.data or None,
            venue_name=form.venue_name.data,
            start_at=form.start_at.data,
            signup_deadline=form.signup_deadline.data,
            max_participants=form.max_participants.data,
            google_maps_url=google_maps_url,
            sponsor_assets=sponsor_assets,
            status="draft",
        )
        db.session.add(tournament)
        db.session.commit()

        current_app.logger.info(
            "Tournament created: id=%s, name=%s, organizer_id=%s",
            tournament.id,
            tournament.name,
            current_user.id,
        )

        flash("OK, il torneo è stato salvato.", "success")
        return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    # POST non valido: logga errori di validazione per debug
    if request.method == "POST":
        current_app.logger.warning("Create tournament: form non valido: %s", form.errors)
        flash("Errore nel form, controlla i campi.", "danger")

    return render_template("tournaments/create.html", form=form)


@tournaments_bp.route("/<int:tournament_id>/edit", methods=["GET", "POST"])
@login_required
def edit(tournament_id: int):
    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.organizer_id != current_user.id:
        flash("You are not allowed to edit this tournament.", "danger")
        return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    form = TournamentForm(obj=tournament)
    # pre-fill sponsor logos textarea
    if request.method == "GET" and tournament.sponsor_assets:
        logos = tournament.sponsor_assets.get("logos", [])
        form.sponsor_logos.data = "\n".join(logos)

    if form.validate_on_submit():
        sponsor_assets = None
        if form.sponsor_logos.data:
            urls = [
                line.strip()
                for line in form.sponsor_logos.data.splitlines()
                if line.strip()
            ]
            sponsor_assets = {"logos": urls}

        tournament.name = form.name.data
        tournament.discipline = form.discipline.data
        tournament.description = form.description.data or None
        tournament.venue_name = form.venue_name.data
        tournament.start_at = form.start_at.data
        tournament.signup_deadline = form.signup_deadline.data
        tournament.max_participants = form.max_participants.data
        tournament.google_maps_url = _normalize_google_maps_input(
            form.google_maps_url.data
        )
        tournament.sponsor_assets = sponsor_assets

        db.session.commit()
        flash("Tournament updated.", "success")
        return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    return render_template("tournaments/create.html", form=form, edit_mode=True)


@tournaments_bp.post("/<int:tournament_id>/delete")
@login_required
def delete(tournament_id: int):
    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.organizer_id != current_user.id:
        flash("You are not allowed to delete this tournament.", "danger")
        return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    db.session.delete(tournament)
    db.session.commit()
    flash("Tournament deleted.", "success")
    return redirect(url_for("tournaments.list_tournaments"))


@tournaments_bp.post("/<int:tournament_id>/generate-bracket")
@login_required
def generate_bracket_now(tournament_id: int):
    """Allow the organizer to force bracket generation for this tournament."""
    tournament = Tournament.query.get_or_404(tournament_id)
    if tournament.organizer_id != current_user.id:
        flash("You are not allowed to generate the bracket for this tournament.", "danger")
        return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    created = _ensure_round1_bracket(tournament.id, ignore_deadline=True)
    if created:
        flash("Bracket generated.", "success")
    else:
        flash(
            "Bracket not generated (already present or not enough participants).",
            "info",
        )
    return redirect(url_for("tournaments.details", tournament_id=tournament.id))
