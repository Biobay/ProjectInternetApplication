from itsdangerous import URLSafeTimedSerializer
from flask import current_app
from flask_mail import Message
from ..extensions import mail


def _get_serializer():
    secret = current_app.config.get("SECRET_KEY")
    salt = current_app.config.get("SECURITY_PASSWORD_SALT", "change-me")
    return URLSafeTimedSerializer(secret, salt=salt)


def generate_confirmation_token(email: str) -> str:
    s = _get_serializer()
    return s.dumps(email)


def confirm_token(token: str, expiration: int = 24 * 3600) -> str:
    s = _get_serializer()
    return s.loads(token, max_age=expiration)


def generate_reset_token(email: str) -> str:
    s = _get_serializer()
    return s.dumps(email)


def confirm_reset_token(token: str, expiration: int = 24 * 3600) -> str:
    s = _get_serializer()
    return s.loads(token, max_age=expiration)


def send_confirmation_email(to_email: str, confirm_url: str) -> None:
    subject = "Confirm your account"
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    body = (
        f"Please confirm your account by clicking the link: {confirm_url}\n\n"
        "This link expires in 24 hours."
    )
    msg = Message(subject=subject, sender=sender, recipients=[to_email], body=body)
    try:
        mail.send(msg)
    except Exception:
        # Mail server might not be configured in development. Silently log instead.
        current_app.logger.info(
            "Confirmation email (dev): %s -> %s", to_email, confirm_url
        )


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    subject = "Reset your password"
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    body = (
        "You requested a password reset.\n\n"
        f"To reset your password, click the link: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    msg = Message(subject=subject, sender=sender, recipients=[to_email], body=body)
    try:
        mail.send(msg)
    except Exception:
        current_app.logger.info(
            "Password reset email (dev): %s -> %s", to_email, reset_url
        )
