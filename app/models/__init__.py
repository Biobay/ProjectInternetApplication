from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_at = db.Column(db.DateTime)

    tournaments = db.relationship("Tournament", back_populates="organizer", lazy="dynamic")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password, method="pbkdf2:sha256")

    def verify_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def get_id(self) -> str:
        return str(self.id)

    # Flask-Login integration
    @property
    def is_authenticated(self) -> bool:  # type: ignore[override]
        return True

    @property
    def is_anonymous(self) -> bool:  # type: ignore[override]
        return False


class Tournament(TimestampMixin, db.Model):
    __tablename__ = "tournaments"

    id = db.Column(db.Integer, primary_key=True)
    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    discipline = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    venue_name = db.Column(db.String(255))
    location_lat = db.Column(db.Float)
    location_lng = db.Column(db.Float)
    google_maps_url = db.Column(db.String(500))
    start_at = db.Column(db.DateTime, nullable=False)
    signup_deadline = db.Column(db.DateTime, nullable=False)
    max_participants = db.Column(db.Integer, nullable=False)
    sponsor_assets = db.Column(db.JSON, default=dict)
    status = db.Column(db.String(50), default="draft", nullable=False)

    organizer = db.relationship("User", back_populates="tournaments")
    participants = db.relationship(
        "TournamentParticipant",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    matches = db.relationship(
        "Match",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )


class TournamentParticipant(TimestampMixin, db.Model):
    __tablename__ = "tournament_participants"
    __table_args__ = (
        db.UniqueConstraint("tournament_id", "license_number", name="uq_license_per_tournament"),
        db.UniqueConstraint("tournament_id", "ranking", name="uq_ranking_per_tournament"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    ranking = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="pending", nullable=False)
    seed = db.Column(db.Integer)

    tournament = db.relationship("Tournament", back_populates="participants")
    user = db.relationship("User")


class Match(TimestampMixin, db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id"), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    bracket_position = db.Column(db.Integer, nullable=False)
    player_a_id = db.Column(db.Integer, db.ForeignKey("tournament_participants.id"))
    player_b_id = db.Column(db.Integer, db.ForeignKey("tournament_participants.id"))
    winner_id = db.Column(db.Integer, db.ForeignKey("tournament_participants.id"))
    report_token = db.Column(db.String(64))
    player_a_reported_winner_id = db.Column(
        db.Integer, db.ForeignKey("tournament_participants.id")
    )
    player_b_reported_winner_id = db.Column(
        db.Integer, db.ForeignKey("tournament_participants.id")
    )

    tournament = db.relationship("Tournament", back_populates="matches")
    player_a = db.relationship(
        "TournamentParticipant", foreign_keys=[player_a_id], uselist=False
    )
    player_b = db.relationship(
        "TournamentParticipant", foreign_keys=[player_b_id], uselist=False
    )
    winner = db.relationship(
        "TournamentParticipant", foreign_keys=[winner_id], uselist=False
    )
    player_a_reported_winner = db.relationship(
        "TournamentParticipant", foreign_keys=[player_a_reported_winner_id], uselist=False
    )
    player_b_reported_winner = db.relationship(
        "TournamentParticipant", foreign_keys=[player_b_reported_winner_id], uselist=False
    )
