from flask import Blueprint, flash, redirect, render_template, request, url_for
from .forms import (
    RegistrationForm,
    LoginForm,
    RequestPasswordResetForm,
    ResetPasswordForm,
)
from .utils import (
    generate_confirmation_token,
    confirm_token,
    send_confirmation_email,
    generate_reset_token,
    confirm_reset_token,
    send_password_reset_email,
)
from ..extensions import db
from ..models import User
from flask_login import login_user, logout_user

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # create inactive user
        user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data.lower(),
            is_active=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        token = generate_confirmation_token(user.email)
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)
        send_confirmation_email(user.email, confirm_url)

        flash("Registration successful — check your email to confirm your account.", "success")
        return redirect(url_for("core.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.verify_password(form.password.data):
            if not user.is_active:
                flash("Please confirm your account before logging in.", "warning")
                return redirect(url_for("auth.login"))
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("core.index"))
        flash("Invalid credentials.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        if user and user.is_active:
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_password_reset_email(user.email, reset_url)

        flash(
            "If that email is registered, you'll receive a reset link shortly.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.get("/logout")
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("core.index"))

@auth_bp.route("/confirm/<token>")
def confirm_email(token: str):
    try:
        email = confirm_token(token, expiration=24 * 3600)
    except Exception:
        flash("The confirmation link is invalid or has expired.", "danger")
        return redirect(url_for("core.index"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("core.index"))

    user.is_active = True
    from datetime import datetime

    user.confirmed_at = datetime.utcnow()
    db.session.add(user)
    db.session.commit()

    flash("Your account has been confirmed. You may now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = confirm_reset_token(token, expiration=24 * 3600)
    except Exception:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Your password has been updated. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
