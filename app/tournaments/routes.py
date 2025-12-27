from datetime import datetime
import re
from typing import Optional

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Tournament, TournamentParticipant
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
                participant = TournamentParticipant(
                    tournament_id=tournament.id,
                    user_id=current_user.id,
                    license_number=application_form.license_number.data,
                    ranking=application_form.ranking.data,
                    status="pending",
                )
                db.session.add(participant)
                db.session.commit()
                flash("Application submitted.", "success")
                return redirect(url_for("tournaments.details", tournament_id=tournament.id))
        elif request.method == "POST":
            flash("You cannot apply to this tournament.", "warning")
            return redirect(url_for("tournaments.details", tournament_id=tournament.id))

    ranked_players_count = (
        TournamentParticipant.query.filter_by(tournament_id=tournament.id)
        .filter(TournamentParticipant.ranking.isnot(None))
        .count()
    )

    return render_template(
        "tournaments/detail.html",
        tournament=tournament,
        application_form=application_form,
        is_organizer=is_organizer,
        is_already_participant=is_already_participant,
        ranked_players_count=ranked_players_count,
    )


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
