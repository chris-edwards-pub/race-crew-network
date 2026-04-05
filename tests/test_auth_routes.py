"""Tests for auth routes — invite email, resend invites, forgot/reset password."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models import SiteSetting, User


def _configure_email(db):
    """Insert a SiteSetting so is_email_configured() returns True."""
    db.session.add(SiteSetting(key="ses_sender", value="noreply@racecrew.net"))
    db.session.commit()


class TestInviteUser:
    def test_invite_creates_user(self, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/users/invite",
            data={"email": "new@example.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        user = User.query.filter_by(email="new@example.com").first()
        assert user is not None
        assert user.invite_token is not None
        assert b"Invite link:" in resp.data

    @patch("app.auth.routes.send_email")
    def test_invite_with_email_sends_email(self, mock_send, logged_in_client, db):
        _configure_email(db)
        resp = logged_in_client.post(
            "/admin/users/invite",
            data={"email": "new@example.com", "send_email_invite": "on"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_send.assert_called_once()
        assert b"Invite email sent to new@example.com" in resp.data

    @patch("app.auth.routes.send_email")
    def test_invite_without_email_checkbox(self, mock_send, logged_in_client, db):
        _configure_email(db)
        resp = logged_in_client.post(
            "/admin/users/invite",
            data={"email": "new@example.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_send.assert_not_called()
        assert b"Invite link:" in resp.data

    @patch(
        "app.auth.routes.send_email",
        side_effect=Exception("SES error"),
    )
    def test_invite_email_failure_still_creates_user(
        self, mock_send, logged_in_client, db
    ):
        _configure_email(db)
        resp = logged_in_client.post(
            "/admin/users/invite",
            data={"email": "new@example.com", "send_email_invite": "on"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        user = User.query.filter_by(email="new@example.com").first()
        assert user is not None
        assert b"Failed to send invite email" in resp.data
        assert b"Invite link:" in resp.data


class TestResendInvites:
    @patch("app.auth.routes.send_email")
    def test_resend_sends_emails(self, mock_send, logged_in_client, db):
        _configure_email(db)
        u1 = User(
            email="p1@test.com",
            password_hash="pending",
            display_name="P1",
            initials="P1",
            invite_token="tok1",
        )
        u2 = User(
            email="p2@test.com",
            password_hash="pending",
            display_name="P2",
            initials="P2",
            invite_token="tok2",
        )
        db.session.add_all([u1, u2])
        db.session.commit()

        resp = logged_in_client.post(
            "/admin/users/resend-invites",
            data={"user_ids": [str(u1.id), str(u2.id)]},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert mock_send.call_count == 2
        assert b"Invite emails sent to 2 user(s)" in resp.data

    @patch("app.auth.routes.send_email")
    def test_resend_skips_active_users(self, mock_send, logged_in_client, db):
        _configure_email(db)
        active = User(
            email="active@test.com",
            password_hash="hashed",
            display_name="Active",
            initials="AC",
            invite_token=None,
        )
        db.session.add(active)
        db.session.commit()

        resp = logged_in_client.post(
            "/admin/users/resend-invites",
            data={"user_ids": [str(active.id)]},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_send.assert_not_called()
        assert b"No pending users in selection" in resp.data

    def test_resend_no_selection(self, logged_in_client, db):
        _configure_email(db)
        resp = logged_in_client.post(
            "/admin/users/resend-invites",
            data={},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"No users selected" in resp.data

    def test_resend_email_not_configured(self, logged_in_client, db):
        resp = logged_in_client.post(
            "/admin/users/resend-invites",
            data={"user_ids": ["1"]},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Email is not configured" in resp.data

    def test_resend_requires_admin(self, app, client, db):
        crew = User(
            email="crew@test.com",
            display_name="Crew",
            initials="CR",
            is_admin=False,
        )
        crew.set_password("password")
        db.session.add(crew)
        db.session.commit()

        client.post(
            "/login",
            data={"email": "crew@test.com", "password": "password"},
            follow_redirects=True,
        )
        resp = client.post(
            "/admin/users/resend-invites",
            data={"user_ids": ["1"]},
            follow_redirects=True,
        )
        assert b"Access denied" in resp.data

    def test_resend_requires_login(self, client):
        resp = client.post("/admin/users/resend-invites")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestAdminUsersPage:
    def test_shows_email_ui_when_configured(self, logged_in_client, db):
        _configure_email(db)
        pending = User(
            email="pending@test.com",
            password_hash="pending",
            display_name="Pending",
            initials="PE",
            invite_token="tok123",
        )
        db.session.add(pending)
        db.session.commit()

        resp = logged_in_client.get("/admin/users")
        assert resp.status_code == 200
        assert b"send_email_invite" in resp.data
        assert b"Resend Invites" in resp.data

    def test_hides_email_ui_when_not_configured(self, logged_in_client, db):
        pending = User(
            email="pending@test.com",
            password_hash="pending",
            display_name="Pending",
            initials="PE",
            invite_token="tok123",
        )
        db.session.add(pending)
        db.session.commit()

        resp = logged_in_client.get("/admin/users")
        assert resp.status_code == 200
        assert b"send_email_invite" not in resp.data
        assert b"Resend Invites" not in resp.data


class TestDeleteUser:
    @patch("app.auth.routes.storage.delete_file")
    def test_delete_user_removes_profile_image(
        self, mock_delete_file, logged_in_client, db
    ):
        user = User(
            email="delete-me@test.com",
            password_hash="pending",
            display_name="Delete Me",
            initials="DM",
            profile_image_key="profile-images/avatar.png",
        )
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/delete",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert db.session.get(User, user.id) is None
        mock_delete_file.assert_called_once_with("profile-images/avatar.png")

    @patch("app.auth.routes.storage.delete_file")
    def test_delete_user_without_profile_image(
        self, mock_delete_file, logged_in_client, db
    ):
        user = User(
            email="no-image@test.com",
            password_hash="pending",
            display_name="No Image",
            initials="NI",
        )
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/delete",
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert db.session.get(User, user.id) is None
        mock_delete_file.assert_not_called()


class TestForgotPassword:
    def test_page_renders(self, client):
        resp = client.get("/forgot-password")
        assert resp.status_code == 200
        assert b"Forgot Password" in resp.data

    @patch("app.auth.routes._send_via_ses")
    def test_sends_email_for_valid_user(self, mock_ses, client, db):
        _configure_email(db)
        user = User(
            email="user@test.com",
            display_name="User",
            initials="US",
        )
        user.set_password("OldPass123")
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/forgot-password",
            data={"email": "user@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"sent a password reset link" in resp.data
        mock_ses.assert_called_once()

        # Token should be set on user
        db.session.refresh(user)
        assert user.reset_token is not None
        assert user.reset_token_expires_at is not None

    @patch("app.auth.routes._send_via_ses")
    def test_generic_message_for_unknown_email(self, mock_ses, client, db):
        _configure_email(db)
        resp = client.post(
            "/forgot-password",
            data={"email": "nobody@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"sent a password reset link" in resp.data
        mock_ses.assert_not_called()

    @patch("app.auth.routes._send_via_ses")
    def test_skips_pending_users(self, mock_ses, client, db):
        _configure_email(db)
        user = User(
            email="pending@test.com",
            password_hash="pending",
            display_name="Pending",
            initials="PE",
            invite_token="some-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/forgot-password",
            data={"email": "pending@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_ses.assert_not_called()

    @patch("app.auth.routes._send_via_ses")
    def test_works_regardless_of_email_opt_in(self, mock_ses, client, db):
        _configure_email(db)
        user = User(
            email="optout@test.com",
            display_name="OptOut",
            initials="OO",
            email_opt_in=False,
        )
        user.set_password("OldPass123")
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/forgot-password",
            data={"email": "optout@test.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_ses.assert_called_once()


class TestResetPassword:
    def _create_user_with_token(self, db, token="valid-token", expired=False):
        user = User(
            email="reset@test.com",
            display_name="Reset",
            initials="RS",
            reset_token=token,
            reset_token_expires_at=(
                datetime.now(timezone.utc) - timedelta(hours=2)
                if expired
                else datetime.now(timezone.utc) + timedelta(hours=1)
            ),
        )
        user.set_password("OldPass123")
        db.session.add(user)
        db.session.commit()
        return user

    def test_renders_with_valid_token(self, client, db):
        self._create_user_with_token(db)
        resp = client.get("/reset-password/valid-token")
        assert resp.status_code == 200
        assert b"Reset Password" in resp.data

    def test_successful_reset(self, client, db):
        user = self._create_user_with_token(db)
        resp = client.post(
            "/reset-password/valid-token",
            data={"password": "NewPass123", "password2": "NewPass123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Your password has been reset" in resp.data

        db.session.refresh(user)
        assert user.reset_token is None
        assert user.reset_token_expires_at is None
        assert user.check_password("NewPass123")

    def test_expired_token_redirects(self, client, db):
        self._create_user_with_token(db, expired=True)
        resp = client.get("/reset-password/valid-token", follow_redirects=True)
        assert b"expired" in resp.data

    def test_invalid_token_404(self, client, db):
        resp = client.get("/reset-password/nonexistent-token")
        assert resp.status_code == 404

    def test_single_use_token(self, client, db):
        self._create_user_with_token(db)
        # Use the token
        client.post(
            "/reset-password/valid-token",
            data={"password": "NewPass123", "password2": "NewPass123"},
        )
        # Try again
        resp = client.get("/reset-password/valid-token")
        assert resp.status_code == 404

    def test_mismatched_passwords(self, client, db):
        self._create_user_with_token(db)
        resp = client.post(
            "/reset-password/valid-token",
            data={"password": "NewPass123", "password2": "Different1"},
            follow_redirects=True,
        )
        assert b"Passwords do not match" in resp.data

    def test_weak_password_rejected(self, client, db):
        self._create_user_with_token(db)
        resp = client.post(
            "/reset-password/valid-token",
            data={"password": "short", "password2": "short"},
            follow_redirects=True,
        )
        assert b"at least 8 characters" in resp.data


class TestPasswordStrength:
    def test_register_rejects_short_password(self, client, db):
        user = User(
            email="new@test.com",
            password_hash="pending",
            display_name="New",
            initials="NW",
            invite_token="reg-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/register/reg-token",
            data={
                "display_name": "New User",
                "initials": "NU",
                "password": "short",
                "password2": "short",
            },
            follow_redirects=True,
        )
        assert b"at least 8 characters" in resp.data

    def test_register_rejects_no_uppercase(self, client, db):
        user = User(
            email="new@test.com",
            password_hash="pending",
            display_name="New",
            initials="NW",
            invite_token="reg-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/register/reg-token",
            data={
                "display_name": "New User",
                "initials": "NU",
                "password": "alllower1",
                "password2": "alllower1",
            },
            follow_redirects=True,
        )
        assert b"uppercase" in resp.data

    def test_register_rejects_no_digit(self, client, db):
        user = User(
            email="new@test.com",
            password_hash="pending",
            display_name="New",
            initials="NW",
            invite_token="reg-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/register/reg-token",
            data={
                "display_name": "New User",
                "initials": "NU",
                "password": "NoDigitHere",
                "password2": "NoDigitHere",
            },
            follow_redirects=True,
        )
        assert b"number" in resp.data

    def test_register_accepts_strong_password(self, client, db):
        user = User(
            email="new@test.com",
            password_hash="pending",
            display_name="New",
            initials="NW",
            invite_token="reg-token",
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            "/register/reg-token",
            data={
                "display_name": "New User",
                "initials": "NU",
                "password": "Strong1Pass",
                "password2": "Strong1Pass",
            },
            follow_redirects=True,
        )
        # Should succeed — no password error messages
        assert b"at least 8 characters" not in resp.data
        assert b"uppercase" not in resp.data
        assert b"number" not in resp.data

    def test_profile_rejects_weak_password(self, logged_in_client, db):
        resp = logged_in_client.post(
            "/profile",
            data={
                "display_name": "Admin",
                "initials": "AD",
                "email": "admin@test.com",
                "password": "weak",
                "password2": "weak",
            },
            follow_redirects=True,
        )
        assert b"at least 8 characters" in resp.data

    def test_profile_saves_bio_and_yacht_club(self, logged_in_client, db, admin_user):
        resp = logged_in_client.post(
            "/profile",
            data={
                "display_name": "Admin",
                "initials": "AD",
                "email": "admin@test.com",
                "yacht_club": "Fishing Bay YC",
                "bio": "Love sailing thistles.",
            },
            follow_redirects=True,
        )
        assert b"Profile updated" in resp.data
        db.session.refresh(admin_user)
        assert admin_user.yacht_club == "Fishing Bay YC"
        assert admin_user.bio == "Love sailing thistles."

    def test_profile_clears_bio_and_yacht_club(self, logged_in_client, db, admin_user):
        admin_user.yacht_club = "Old Club"
        admin_user.bio = "Old bio"
        db.session.commit()

        resp = logged_in_client.post(
            "/profile",
            data={
                "display_name": "Admin",
                "initials": "AD",
                "email": "admin@test.com",
                "yacht_club": "",
                "bio": "",
            },
            follow_redirects=True,
        )
        assert b"Profile updated" in resp.data
        db.session.refresh(admin_user)
        assert admin_user.yacht_club is None
        assert admin_user.bio is None

    def test_view_profile_shows_bio_and_yacht_club(
        self, logged_in_client, db, admin_user
    ):
        other = User(
            email="sailor@test.com",
            display_name="Sailor",
            initials="SL",
            yacht_club="Hampton YC",
            bio="Weekend racer",
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_client.get(f"/crew/{other.id}")
        assert b"Hampton YC" in resp.data
        assert b"Weekend racer" in resp.data

    def test_view_profile_hides_empty_bio_and_yacht_club(
        self, logged_in_client, db, admin_user
    ):
        other = User(
            email="sailor@test.com",
            display_name="Sailor",
            initials="SL",
        )
        other.set_password("password")
        db.session.add(other)
        db.session.commit()

        resp = logged_in_client.get(f"/crew/{other.id}")
        assert b"Yacht Club" not in resp.data
        assert b"About" not in resp.data

    def test_admin_edit_user_rejects_weak_password(self, logged_in_client, db):
        user = User(
            email="target@test.com",
            display_name="Target",
            initials="TG",
        )
        user.set_password("OldPass123")
        db.session.add(user)
        db.session.commit()

        resp = logged_in_client.post(
            f"/admin/users/{user.id}/edit",
            data={
                "display_name": "Target",
                "initials": "TG",
                "email": "target@test.com",
                "password": "weak",
            },
            follow_redirects=True,
        )
        assert b"at least 8 characters" in resp.data
