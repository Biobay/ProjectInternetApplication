from flask import Flask

from .auth.routes import auth_bp
from .core.routes import core_bp
from .matches.routes import matches_bp
from .tournaments.routes import tournaments_bp
from .users.routes import users_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(tournaments_bp, url_prefix="/tournaments")
    app.register_blueprint(matches_bp, url_prefix="/matches")
    app.register_blueprint(users_bp, url_prefix="/me")
