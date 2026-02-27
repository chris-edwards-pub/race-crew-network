"""Tests for the Flask app factory and core setup."""

from app import __version__, create_app


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
