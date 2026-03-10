"""Tests for the Flask app factory and core setup."""

from datetime import date

from app import __version__, create_app
from app import db as _db
from app.models import SiteSetting, User


class TestAppFactory:
    def test_create_app_returns_flask_app(self):
        app = create_app()
        assert app is not None
        assert app.name == "app"

    def test_testing_config(self, app):
        assert app.config["TESTING"] is True

    def test_version_is_set(self):
        assert __version__
        parts = __version__.split(".")
        assert len(parts) == 3

    def test_blueprints_registered(self, app):
        assert "admin" in app.blueprints
        assert "auth" in app.blueprints
        assert "regattas" in app.blueprints
        assert "calendar" in app.blueprints

    def test_version_in_context(self, client):
        resp = client.get("/login", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Race Crew Network" in resp.data

    def test_ga_script_not_rendered_in_testing(self, app, client, db):
        setting = SiteSetting(key="ga_measurement_id", value="G-TESTHIDDEN")
        db.session.add(setting)
        db.session.commit()

        resp = client.get("/", follow_redirects=True)
        assert resp.status_code == 200
        assert b"googletagmanager.com/gtag/js" not in resp.data

    def test_ga_script_rendered_in_production_mode(self):
        app = create_app(
            test_config={
                "TESTING": False,
                "ENV": "production",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "prod.example",
                "ANTHROPIC_API_KEY": "test-key",
            }
        )

        with app.app_context():
            _db.create_all()
            setting = SiteSetting(key="ga_measurement_id", value="G-SHOWME123")
            _db.session.add(setting)
            _db.session.commit()

            client = app.test_client()
            resp = client.get("/", base_url="http://prod.example")
            assert resp.status_code == 200
            assert b"googletagmanager.com/gtag/js?id=G-SHOWME123" in resp.data

            _db.drop_all()

    def test_admin_nav_contains_analytics_link(self, app, client, db):
        user = User(
            email="admin2@test.com",
            display_name="Admin Two",
            initials="A2",
            is_admin=True,
            is_skipper=True,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "admin2@test.com", "password": "password"},
            follow_redirects=True,
        )

        resp = client.get("/")
        assert resp.status_code == 200
        assert b">My Crew<" in resp.data
        assert b">Import<" in resp.data
        assert b"/admin/users" in resp.data
        assert b"/admin/settings/analytics" in resp.data

    def test_regatta_days_filter_single_day(self, app):
        with app.app_context():
            fn = app.jinja_env.filters["regatta_days"]
            assert fn(date(2026, 7, 11), None) == "Sat"

    def test_regatta_days_filter_two_day_range(self, app):
        with app.app_context():
            fn = app.jinja_env.filters["regatta_days"]
            assert fn(date(2026, 7, 11), date(2026, 7, 12)) == "Sat & Sun"

    def test_regatta_days_filter_multi_day_range(self, app):
        with app.app_context():
            fn = app.jinja_env.filters["regatta_days"]
            assert fn(date(2026, 7, 11), date(2026, 7, 13)) == "Sat thru Mon"
