from flask import Flask, flash, has_request_context, redirect, request, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup, escape
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import RequestEntityTooLarge

__version__ = "0.55.0"

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None
csrf = CSRFProtect()


def _avatar_svg_markup(user, size=20):
    """Render a Multiavatar inline SVG for a user-like object."""
    from multiavatar.multiavatar import multiavatar

    key = user.avatar_key if hasattr(user, "avatar_key") else str(user)
    svg = multiavatar(key, None, None)
    return Markup(
        f'<span class="avatar-icon" style="display:inline-block;'
        f"width:{size}px;height:{size}px;vertical-align:middle;"
        f'">{svg}</span>'
    )


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("app.config.Config")
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.calendar import bp as calendar_bp
    from app.email import bp as email_bp
    from app.regattas import bp as regattas_bp
    from app.storage_routes import bp as storage_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(regattas_bp)
    app.register_blueprint(storage_bp)

    from app.commands import register_commands

    register_commands(app)

    @app.context_processor
    def inject_version():
        return {"app_version": __version__}

    @app.context_processor
    def inject_profile_image():
        from flask_login import current_user as cu

        url = None
        if cu.is_authenticated and cu.profile_image_key:
            try:
                from app import storage

                url = storage.get_file_url(cu.profile_image_key)
            except Exception:
                pass
        return {"current_user_profile_image_url": url}

    @app.context_processor
    def inject_site_settings():
        from app.models import SiteSetting

        ga_measurement_id = ""
        try:
            ga_setting = SiteSetting.query.filter_by(key="ga_measurement_id").first()
            if ga_setting and ga_setting.value:
                ga_measurement_id = ga_setting.value.strip()
        except SQLAlchemyError as exc:
            app.logger.warning("Unable to load GA setting from database: %s", exc)
            ga_measurement_id = ""

        is_local_host = False
        if has_request_context():
            host = (request.host or "").split(":", 1)[0].lower()
            is_local_host = host in {"localhost", "127.0.0.1"}

        # Disable GA only for tests and local hosts.
        is_dev_or_test = bool(app.config.get("TESTING")) or is_local_host

        return {
            "ga_measurement_id": ga_measurement_id,
            "is_dev_or_test": is_dev_or_test,
        }

    @app.template_filter("avatar_svg")
    def avatar_svg_filter(user, size=20):
        """Render a Multiavatar inline SVG for a user."""
        return _avatar_svg_markup(user, size)

    @app.template_filter("user_icon")
    def user_icon_filter(user, size=20):
        """Render profile picture when present; otherwise render avatar fallback."""
        if user and getattr(user, "profile_image_key", None):
            try:
                from app import storage

                image_url = escape(storage.get_file_url(user.profile_image_key))
                display_name = escape(getattr(user, "display_name", "User"))
                return Markup(
                    f'<span class="avatar-icon" style="display:inline-block;'
                    f"width:{size}px;height:{size}px;vertical-align:middle;"
                    '">'
                    f'<img class="avatar-photo" src="{image_url}" alt="{display_name}" '
                    f'style="width:100%;height:100%;border-radius:50%;object-fit:cover;">'
                    "</span>"
                )
            except Exception:
                # Fall through to avatar rendering if image URL generation fails.
                pass

        return _avatar_svg_markup(user, size)

    @app.template_filter("sort_rsvps")
    def sort_rsvps(rsvps):
        order = {"yes": 0, "no": 1, "maybe": 2}
        return sorted(
            rsvps, key=lambda r: (order.get(r.status, 3), r.user.display_name)
        )

    @app.template_filter("regatta_days")
    def regatta_days(start_date, end_date=None):
        if not start_date:
            return ""

        if not end_date or end_date <= start_date:
            return start_date.strftime("%a")

        day_span = (end_date - start_date).days
        if day_span == 1:
            return f"{start_date.strftime('%a')} & {end_date.strftime('%a')}"

        return f"{start_date.strftime('%a')} thru {end_date.strftime('%a')}"

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(_exc):
        max_mb = int(app.config.get("PROFILE_IMAGE_MAX_BYTES", 10 * 1024 * 1024)) // (
            1024 * 1024
        )
        flash(f"Profile picture must be {max_mb} MB or smaller.", "error")
        if request.path == url_for("auth.profile"):
            return redirect(url_for("auth.profile"))
        return redirect(request.referrer or url_for("regattas.index"))

    return app
