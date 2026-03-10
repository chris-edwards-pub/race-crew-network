"""Tests for auth routes — invite email and resend invites."""

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
