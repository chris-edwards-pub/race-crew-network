"""Tests for the Multiavatar user icon feature."""

import secrets
from datetime import date
from unittest.mock import patch

from app.models import RSVP, Regatta, User


class TestAvatarKeyProperty:
    def test_avatar_key_defaults_to_email(self, db, admin_user):
        assert admin_user.avatar_seed is None
        assert admin_user.avatar_key == admin_user.email

    def test_avatar_key_uses_seed_when_set(self, db, admin_user):
        admin_user.avatar_seed = "custom-seed"
        db.session.commit()
        assert admin_user.avatar_key == "custom-seed"


class TestAvatarSvgFilter:
    def test_filter_returns_svg_markup(self, app, db, admin_user):
        with app.app_context():
            env = app.jinja_env
            tmpl = env.from_string("{{ user|avatar_svg(20) }}")
            result = tmpl.render(user=admin_user)
            assert "<svg" in result
            assert "avatar-icon" in result

    def test_filter_different_users_produce_different_svgs(self, app, db, admin_user):
        user2 = User(
            email="different@test.com",
            display_name="Different",
            initials="DF",
        )
        user2.set_password("password")
        db.session.add(user2)
        db.session.commit()

        with app.app_context():
            env = app.jinja_env
            tmpl = env.from_string("{{ user|avatar_svg(20) }}")
            svg1 = tmpl.render(user=admin_user)
            svg2 = tmpl.render(user=user2)
            assert svg1 != svg2


class TestUserIconFilter:
    def test_user_icon_falls_back_to_avatar_without_profile_picture(
        self, app, db, admin_user
    ):
        with app.app_context():
            env = app.jinja_env
            tmpl = env.from_string("{{ user|user_icon(20) }}")
            result = tmpl.render(user=admin_user)
            assert "<svg" in result
            assert "avatar-icon" in result

    @patch("app.storage.get_file_url", return_value="https://s3.example.com/pic.jpg")
    def test_user_icon_prefers_profile_picture_when_available(
        self, mock_get_url, app, db, admin_user
    ):
        app.config["BUCKET_NAME"] = "test-bucket"
        admin_user.profile_image_key = "profile-images/admin.jpg"
        db.session.commit()

        with app.app_context():
            env = app.jinja_env
            tmpl = env.from_string("{{ user|user_icon(20) }}")
            result = tmpl.render(user=admin_user)
            assert "<img" in result
            assert "https://s3.example.com/pic.jpg" in result
            assert "<svg" not in result

        mock_get_url.assert_called_once_with("profile-images/admin.jpg")


class TestAvatarInSchedule:
    def _setup_regatta_with_rsvp(self, db, admin_user):
        regatta = Regatta(
            name="Test Regatta",
            location="Test Location",
            start_date=date(2026, 6, 15),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=admin_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()
        return regatta

    def test_avatar_in_schedule_page(self, logged_in_client, admin_user, db):
        self._setup_regatta_with_rsvp(db, admin_user)
        resp = logged_in_client.get("/")
        html = resp.data.decode()
        assert "avatar-icon" in html
        assert "<svg" in html

    def test_avatar_in_navbar(self, logged_in_client, admin_user, db):
        resp = logged_in_client.get("/")
        html = resp.data.decode()
        # Navbar should contain avatar + initials
        assert "avatar-icon" in html
        assert admin_user.initials in html


class TestAvatarRegeneration:
    def test_profile_saves_avatar_seed(self, logged_in_client, admin_user, db):
        logged_in_client.post(
            "/profile",
            data={
                "display_name": "Admin",
                "initials": "AD",
                "email": "admin@test.com",
                "avatar_seed": "my-custom-seed",
            },
            follow_redirects=True,
        )
        db.session.refresh(admin_user)
        assert admin_user.avatar_seed == "my-custom-seed"
        assert admin_user.avatar_key == "my-custom-seed"

    def test_profile_clears_avatar_seed_when_empty(
        self, logged_in_client, admin_user, db
    ):
        admin_user.avatar_seed = "old-seed"
        db.session.commit()

        logged_in_client.post(
            "/profile",
            data={
                "display_name": "Admin",
                "initials": "AD",
                "email": "admin@test.com",
                "avatar_seed": "",
            },
            follow_redirects=True,
        )
        db.session.refresh(admin_user)
        assert admin_user.avatar_seed is None
        assert admin_user.avatar_key == admin_user.email


class TestAvatarInViewProfile:
    def test_view_profile_shows_avatar(self, logged_in_client, admin_user, db):
        resp = logged_in_client.get(f"/crew/{admin_user.id}")
        html = resp.data.decode()
        assert "avatar-icon" in html


class TestAvatarInIcal:
    def test_ical_does_not_break(self, logged_in_client, admin_user, db):
        """iCal is text-only so just ensure it still works."""
        admin_user.calendar_token = secrets.token_urlsafe(32)
        regatta = Regatta(
            name="Test Regatta",
            location="Test Location",
            start_date=date(2026, 6, 15),
            created_by=admin_user.id,
        )
        db.session.add(regatta)
        db.session.flush()
        rsvp = RSVP(regatta_id=regatta.id, user_id=admin_user.id, status="yes")
        db.session.add(rsvp)
        db.session.commit()

        resp = logged_in_client.get(f"/calendar/{admin_user.calendar_token}.ics")
        assert resp.status_code == 200
        data = resp.data.decode()
        assert "AD" in data
