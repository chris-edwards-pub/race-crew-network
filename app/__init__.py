from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

__version__ = "0.17.0"

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.auth import bp as auth_bp
    from app.calendar import bp as calendar_bp
    from app.regattas import bp as regattas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(regattas_bp)

    from app.commands import register_commands

    register_commands(app)

    @app.context_processor
    def inject_version():
        return {"app_version": __version__}

    @app.template_filter("sort_rsvps")
    def sort_rsvps(rsvps):
        order = {"yes": 0, "no": 1, "maybe": 2}
        return sorted(rsvps, key=lambda r: (order.get(r.status, 3), r.user.display_name))

    return app
