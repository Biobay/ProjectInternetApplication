from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import DateTimeField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError


class TournamentForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=255)])
    discipline = SelectField(
        "Discipline",
        choices=[
            ("tennis", "Tennis"),
            ("chess", "Chess"),
            ("football", "Football"),
            ("paddle", "Paddle"),
        ],
        validators=[DataRequired()],
    )
    venue_name = StringField("Location", validators=[DataRequired(), Length(max=255)])
    start_at = DateTimeField("Start date and time", validators=[DataRequired()], format="%Y-%m-%dT%H:%M")
    signup_deadline = DateTimeField(
        "Signup deadline",
        validators=[DataRequired()],
        format="%Y-%m-%dT%H:%M",
    )
    max_participants = IntegerField(
        "Max participants", validators=[DataRequired(), NumberRange(min=2)]
    )
    description = TextAreaField("Description", validators=[Length(max=2000)])
    google_maps_url = StringField(
        "Google Maps URL (puoi incollare anche l'iframe)",
        validators=[Length(max=2000)],
    )
    sponsor_logos = TextAreaField(
        "Sponsor logos (one URL per line)", validators=[Length(max=2000)]
    )

    def validate_start_at(self, field: DateTimeField) -> None:
        if field.data <= datetime.utcnow():
            raise ValidationError("Start date must be in the future.")

    def validate_signup_deadline(self, field: DateTimeField) -> None:
        if field.data <= datetime.utcnow():
            raise ValidationError("Signup deadline must be in the future.")
        if self.start_at.data and field.data >= self.start_at.data:
            raise ValidationError("Signup deadline must be before the start date.")


class TournamentApplicationForm(FlaskForm):
    license_number = StringField(
        "License number", validators=[DataRequired(), Length(max=50)]
    )
    ranking = IntegerField(
        "Ranking", validators=[DataRequired(), NumberRange(min=1)]
    )
