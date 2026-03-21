"""Tests for the Multiavatar user icon feature."""

import secrets
from datetime import date
from unittest.mock import patch

from app.models import RSVP, Regatta, User


class TestGenerateAvatarSeed:
    def test_returns_prefixed_string(self):
        seed = User.generate_avatar_seed()
        assert seed.startswith("avatar-")

    def test_returns_unique_values(self):
        seeds = {User.generate_avatar_seed() for _ in range(50)}
        assert len(seeds) == 50

    def test_seed_has_expected_length(self):
        seed = User.generate_avatar_seed()
        # "avatar-" (7) + 24 hex chars = 31
        assert len(seed) == 31


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


class TestAutoAvatarSeedOnInvite:
    def test_invite_user_sets_avatar_seed(self, logged_in_client, admin_user, db):
        resp = logged_in_client.post(
            "/admin/users/invite",
            data={"email": "newuser@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        user = User.query.filter_by(email="newuser@test.com").first()
        assert user is not None
        assert user.avatar_seed is not None
        assert user.avatar_seed.startswith("avatar-")

    def test_invite_crew_sets_avatar_seed(self, logged_in_client, admin_user, db):
        resp = logged_in_client.post(
            "/my-crew/invite",
            data={"email": "crewnew@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        user = User.query.filter_by(email="crewnew@test.com").first()
        assert user is not None
        assert user.avatar_seed is not None
        assert user.avatar_seed.startswith("avatar-")


class TestAutoAvatarSeedOnRegister:
    def test_register_backfills_seed_if_missing(self, client, db, admin_user):
        """Legacy invited users without avatar_seed get one on registration."""
        user = User(
            email="legacy@test.com",
            password_hash="pending",
            display_name="legacy@test.com",
            initials="??",
            invite_token="legacy-token-123",
            invited_by=admin_user.id,
        )
        db.session.add(user)
        db.session.commit()
        assert user.avatar_seed is None

        client.post(
            "/register/legacy-token-123",
            data={
                "display_name": "Legacy User",
                "initials": "LU",
                "password": "Password123",
                "password2": "Password123",
            },
            follow_redirects=True,
        )
        db.session.refresh(user)
        assert user.invite_token is None
        assert user.avatar_seed is not None
        assert user.avatar_seed.startswith("avatar-")

    def test_register_preserves_existing_seed(self, client, db, admin_user):
        """Users who already have avatar_seed keep it on registration."""
        user = User(
            email="seeded@test.com",
            password_hash="pending",
            display_name="seeded@test.com",
            initials="??",
            invite_token="seeded-token-456",
            invited_by=admin_user.id,
            avatar_seed="avatar-existing-seed",
        )
        db.session.add(user)
        db.session.commit()

        client.post(
            "/register/seeded-token-456",
            data={
                "display_name": "Seeded User",
                "initials": "SU",
                "password": "Password123",
                "password2": "Password123",
            },
            follow_redirects=True,
        )
        db.session.refresh(user)
        assert user.avatar_seed == "avatar-existing-seed"


class TestCliAvatarSeed:
    def test_init_admin_sets_avatar_seed(self, app, db):
        runner = app.test_cli_runner()
        result = runner.invoke(
            args=["init-admin"],
            env={
                "INIT_ADMIN_EMAIL": "cliadmin@test.com",
                "INIT_ADMIN_PASSWORD": "password123",
            },
        )
        assert result.exit_code == 0
        user = User.query.filter_by(email="cliadmin@test.com").first()
        assert user is not None
        assert user.avatar_seed is not None
        assert user.avatar_seed.startswith("avatar-")

    def test_create_admin_sets_avatar_seed(self, app, db):
        runner = app.test_cli_runner()
        result = runner.invoke(
            args=[
                "create-admin",
                "--email",
                "cliadmin2@test.com",
                "--password",
                "password123",
                "--name",
                "CLI Admin",
                "--initials",
                "CA",
            ],
        )
        assert result.exit_code == 0
        user = User.query.filter_by(email="cliadmin2@test.com").first()
        assert user is not None
        assert user.avatar_seed is not None
        assert user.avatar_seed.startswith("avatar-")
