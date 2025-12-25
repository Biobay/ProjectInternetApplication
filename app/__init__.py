from typing import Optional

from flask import Flask

from . import config
from .blueprints import register_blueprints
from .cli import register_cli_commands
from .extensions import csrf, db, limiter, login_manager, mail, migrate


def create_app(config_name: Optional[str] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    cfg = config.get_config(config_name)
    app.config.from_object(cfg)

    register_extensions(app)
    register_blueprints(app)
    register_cli_commands(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    # user loader for Flask-Login
    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None
