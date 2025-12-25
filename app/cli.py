import click
from flask import Flask

from .extensions import db


def register_cli_commands(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.argument("email")
    def create_admin(email: str) -> None:
        """Create an admin user placeholder."""
        from .models import User

        user = User.query.filter_by(email=email).first()
        if user:
            click.echo("User already exists")
            return
        user = User(
            first_name="Admin",
            last_name="User",
            email=email,
            is_active=True,
        )
        user.set_password("ChangeMe123!")
        db.session.add(user)
        db.session.commit()
        click.echo("Admin user created")
